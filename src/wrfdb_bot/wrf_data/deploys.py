"""Which WRFrontiersDB-Data commit the frontends (Site, Discount Visualizer) serve.

Each frontend's build writes a deploy record and serves it as `<url>/deploy.json`:
the Data commit, date and version it was built from, its CI run, and the build
time (fields documented in WRFrontiersDB-Data's `tools/wrfdb_data/deploy_record.py`).
The pipeline copies the record of each Site deploy it makes into its deploy state
file (`SITE_DEPLOY_STATE`), which the DataStore watches to know when to re-fetch the
Site's meta descriptions.
"""

import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

FETCH_TIMEOUT_SECONDS = 15


class DeployError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeployRecord:
    run_id: str
    """The CI run that built it; run ids only grow."""
    data_commit: str
    data_version: str
    built_at_utc: str | None = None
    run_url: str | None = None

    @property
    def short_commit(self) -> str:
        return self.data_commit[:7]

    @classmethod
    def from_doc(cls, doc: object, source: str) -> 'DeployRecord':
        if not isinstance(doc, dict):
            raise DeployError(f'{source} is not a JSON object')
        run_id, commit = doc.get('run_id'), doc.get('data_commit')
        if not run_id or not str(run_id).isdigit() or not commit:
            raise DeployError(f'{source} has no valid run_id / data_commit')
        return cls(str(run_id), str(commit), str(doc.get('data_version') or ''),
                   doc.get('built_at_utc'), doc.get('run_url'))


def read_state(state_file: Path) -> DeployRecord | None:
    """The pipeline's last recorded deploy, or None if none is recorded yet."""
    try:
        doc = json.loads(state_file.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise DeployError(f'Deploy state {state_file} unreadable: {e}') from e
    return DeployRecord.from_doc(doc, f'Deploy state {state_file}')


def fetch_live(site_url: str) -> DeployRecord:
    """The record a frontend serves now (cache-busted)."""
    url = f'{site_url.rstrip("/")}/deploy.json'
    try:
        with urllib.request.urlopen(f'{url}?t={int(time.time())}', timeout=FETCH_TIMEOUT_SECONDS) as response:
            doc = json.load(response)
    except (OSError, ValueError) as e:
        raise DeployError(f'Could not fetch {url}: {e}') from e
    return DeployRecord.from_doc(doc, url)
