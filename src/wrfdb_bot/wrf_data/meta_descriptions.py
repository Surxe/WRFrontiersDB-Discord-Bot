"""Object page meta descriptions, as published by the Site at `/meta_descriptions.json`.

The Site writes each object page's meta description (per language) and bakes the
same text into that JSON when it builds. The bot uses the English one as an embed's
description, so embeds read like the page's link preview. For armor modules the Site
also publishes the description split into its lead text and its stats
(`stat_summaries`), so the stats can be shown as embed fields.

When to fetch is driven by the pipeline: after each successful Site deploy it writes
the deploy's record (`deploys.py`) to a state file, including its CI run's id. The
Site's JSON carries the id of the run that built it (`build_id`), so a fetch can tell
the new build from a copy the CDN still has cached.
"""

import json
import urllib.request
from dataclasses import dataclass, field

FETCH_TIMEOUT_SECONDS = 30

Descriptions = dict[str, dict[str, dict[str, str]]]
"""Object type name -> object id -> language -> description."""


StatField = tuple[str, str]
"""A stat as (name, value), e.g. ('Max Speed', '109km/h')."""


@dataclass(frozen=True)
class StatSummary:
    lead: str
    """The description without its stats (a torso's ability text); '' for none."""
    rows: tuple[tuple[StatField, ...], ...]
    """The stats, grouped the way the Site lays them out."""

    @property
    def fields(self) -> tuple[StatField, ...]:
        return tuple(f for row in self.rows for f in row)


class MetaDescriptionsError(RuntimeError):
    pass


@dataclass(frozen=True)
class MetaDescriptions:
    build_id: str | None = None
    """The Site CI run that built them; None if never fetched or built locally."""
    version: str | None = None
    """The game version of the data the Site was built from."""
    descriptions: Descriptions = field(default_factory=dict)
    stat_summaries: dict = field(default_factory=dict)
    """Module id -> language -> {lead, rows: [[{name, value}]]}, as the Site publishes it."""

    def stat_summary(self, object_id: str, lang: str = 'en') -> StatSummary | None:
        raw = self.stat_summaries.get(object_id, {}).get(lang)
        if not raw:
            return None
        rows = tuple(
            tuple((f['name'], f['value']) for f in row if f.get('name') and f.get('value'))
            for row in raw.get('rows', [])
        )
        return StatSummary(raw.get('lead', ''), tuple(row for row in rows if row))

    def get(self, object_type_name: str, object_id: str, lang: str = 'en') -> str:
        return self.descriptions.get(object_type_name, {}).get(object_id, {}).get(lang, '')

    def is_older_than(self, run_id: str) -> bool:
        """Whether a deploy by `run_id` is newer than these (run ids only grow)."""
        return not (self.build_id and self.build_id.isdigit()) or int(self.build_id) < int(run_id)


def fetch(site_url: str, run_id: str | None) -> MetaDescriptions:
    """Fetch the Site's meta descriptions; `run_id` also busts the CDN cache."""
    url = f'{site_url.rstrip("/")}/meta_descriptions.json'
    if run_id:
        url += f'?build={run_id}'
    try:
        with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_SECONDS) as response:
            doc = json.load(response)
    except (OSError, ValueError) as e:
        raise MetaDescriptionsError(f'Could not fetch {url}: {e}') from e
    if not isinstance(doc, dict) or not isinstance(doc.get('descriptions'), dict):
        raise MetaDescriptionsError(f'{url} has no descriptions object')
    build_id = doc.get('build_id')
    return MetaDescriptions(
        build_id=str(build_id) if build_id is not None else None,
        version=doc.get('version'),
        descriptions=doc['descriptions'],
        stat_summaries=doc.get('stat_summaries') or {},
    )
