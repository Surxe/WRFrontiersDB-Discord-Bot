import io
import json
import subprocess

import pytest

from wrfdb_bot.wrf_data import deploys
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.deploys import DeployError, DeployRecord

DOC = {'run_id': '42', 'data_commit': 'abcdef1234', 'data_version': '2026-01-01', 'built_at_utc': 'x'}


class TestDeployRecord:
    def test_from_doc(self):
        record = DeployRecord.from_doc(DOC, 'test')
        assert record.run_id == '42'
        assert record.short_commit == 'abcdef1'
        assert record.data_version == '2026-01-01'

    @pytest.mark.parametrize(
        'doc', [[], {'run_id': '42'}, {'data_commit': 'abc'}, {'run_id': 'x', 'data_commit': 'abc'}]
    )
    def test_invalid(self, doc):
        with pytest.raises(DeployError):
            DeployRecord.from_doc(doc, 'test')

    def test_read_state(self, tmp_path):
        state = tmp_path / 'state.json'
        assert deploys.read_state(state) is None
        state.write_text(json.dumps(DOC))
        assert deploys.read_state(state).run_id == '42'
        state.write_text('not json')
        with pytest.raises(DeployError):
            deploys.read_state(state)

    def test_fetch_live(self, monkeypatch):
        urls = []

        def urlopen(url, timeout):
            urls.append(url)
            return io.BytesIO(json.dumps(DOC).encode())

        monkeypatch.setattr(deploys.urllib.request, 'urlopen', urlopen)
        assert deploys.fetch_live('https://example.invalid/').data_commit == 'abcdef1234'
        assert urls[0].startswith('https://example.invalid/deploy.json?t=')

    def test_fetch_live_unreachable(self, monkeypatch):
        def urlopen(url, timeout):
            raise OSError('down')

        monkeypatch.setattr(deploys.urllib.request, 'urlopen', urlopen)
        with pytest.raises(DeployError):
            deploys.fetch_live('https://example.invalid')


def git(repo, *args):
    env = {'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't',
           'GIT_COMMITTER_EMAIL': 't@t', 'PATH': '/usr/bin:/bin'}
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True,
                          env=env).stdout.strip()


class TestDataRepoCommits:
    def test_commits(self, tmp_path):
        git(tmp_path, 'init', '-q')
        git(tmp_path, 'commit', '-q', '--allow-empty', '-m', 'a')
        old = git(tmp_path, 'rev-parse', 'HEAD')
        git(tmp_path, 'commit', '-q', '--allow-empty', '-m', 'b')
        git(tmp_path, 'commit', '-q', '--allow-empty', '-m', 'c')
        repo = DataRepo(tmp_path)
        head = repo.read_commit()
        assert head != old
        assert repo.count_commits(old, head) == 2
        assert repo.is_ancestor(old, head)
        assert not repo.is_ancestor(head, old)
        assert repo.count_commits('f' * 40, head) is None

    def test_not_a_checkout(self, tmp_path):
        assert DataRepo(tmp_path).read_commit() is None
