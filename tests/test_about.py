from test_deploys import git

from wrfdb_bot.services.about.cog import status_embed
from wrfdb_bot.services.about.status import gather, relation
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.deploys import DeployError, DeployRecord


def history(tmp_path) -> tuple[DataRepo, list[str]]:
    """A Data clone with three commits; returns it and their shas, oldest first."""
    git(tmp_path, 'init', '-q')
    shas = []
    for message in 'abc':
        git(tmp_path, 'commit', '-q', '--allow-empty', '-m', message)
        shas.append(git(tmp_path, 'rev-parse', 'HEAD'))
    return DataRepo(tmp_path), shas


class TestRelation:
    def test_relations(self, tmp_path):
        repo, (a, b, c) = history(tmp_path)
        assert relation(repo, b, b) == 'same as the bot'
        assert relation(repo, c, a) == '2 commit(s) behind the bot'
        assert relation(repo, a, c) == '2 commit(s) ahead of the bot'
        assert relation(repo, c, 'f' * 40) == "not in the bot's Data clone"
        assert relation(repo, None, a) == "the bot's Data commit is unknown"


class TestGather:
    def test_gather_and_embed(self, tmp_path, store):
        repo, (a, _b, c) = history(tmp_path)
        records = {'https://site': DeployRecord('7', a, '2026-01-01', '2026-01-02T03:04:05Z', 'https://run/7')}

        def fetch_live(url):
            if url not in records:
                raise DeployError(f'Could not fetch {url}/deploy.json: 404')
            return records[url]

        status = gather(store.snapshot, repo, {'Site': 'https://site', 'Visualizer': 'https://vis'}, fetch_live)
        assert status.bot_commit == c
        site, vis = status.frontends
        assert site.relation == '2 commit(s) behind the bot'
        assert vis.record is None and '404' in vis.relation

        embed = status_embed(status)
        fields = {f.name: f.value for f in embed.fields}
        assert fields['Bot'] == f'Data 2026-01-01 - `{c[:7]}`'
        assert fields['Site'].startswith(f'Data 2026-01-01 - `{a[:7]}` - 2 commit(s) behind the bot')
        assert 'Built 2026-01-02 03:04:05 UTC ([run](https://run/7))' in fields['Site']
        assert '404' in fields['Visualizer']
