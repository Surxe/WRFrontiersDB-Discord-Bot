import json

import pytest
from conftest import SITE_URL

from wrfdb_bot.services.lookup.index import LookupIndex
from wrfdb_bot.wrf_data import meta_descriptions
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.meta_descriptions import MetaDescriptions, MetaDescriptionsError
from wrfdb_bot.wrf_data import store as store_module
from wrfdb_bot.wrf_data.store import DataStore

KATE = 'DA_Pilot_Rare_KateSinclair.0'


def meta(build_id: str | None, kate: str = 'L1: Vanguard\nL2: Tactician') -> MetaDescriptions:
    return MetaDescriptions(build_id, '2026-01-01', {'Pilot': {KATE: {'en': kate, 'de': 'Deutsch'}}})


class FakeSite:
    """Stands in for meta_descriptions.fetch: serves `served`, records each fetch."""

    def __init__(self, served: MetaDescriptions):
        self.served = served
        self.calls: list[str | None] = []

    def __call__(self, site_url: str, run_id: str | None) -> MetaDescriptions:
        assert site_url == SITE_URL
        self.calls.append(run_id)
        if isinstance(self.served, Exception):
            raise self.served
        return self.served


@pytest.fixture
def deploy_state(tmp_path):
    return tmp_path / 'site_deploy_state.json'


def record_deploy(path, run_id: str) -> None:
    path.write_text(json.dumps(deploy_doc(run_id)))


def deploy_doc(run_id: str, data_commit: str = 'abcdef1234', data_version: str = '2026-01-01') -> dict:
    """A deploy record, as the pipeline writes it to its Site deploy state."""
    return {'run_id': run_id, 'data_commit': data_commit, 'data_version': data_version,
            'built_at_utc': '2026-01-01T00:00:00Z', 'run_url': f'https://example.invalid/{run_id}'}


def make_store(data_dir, deploy_state, site: FakeSite, monkeypatch) -> DataStore:
    monkeypatch.setattr(meta_descriptions, 'fetch', site)
    store = DataStore(DataRepo(data_dir), SITE_URL, deploy_state)
    store.load()
    return store


ALPHA_TORSO = 'DA_Module_TorsoAlpha.0'


def meta_with_stats(build_id: str = '1') -> MetaDescriptions:
    summary = {
        'lead': 'Pulls a target in.',
        'rows': [
            [{'name': 'Weight used', 'value': '11'}, {'name': 'Armor', 'value': '63,800'}],
            [{'name': 'Shield', 'value': '29,000'}],
        ],
    }
    return MetaDescriptions(
        build_id,
        '2026-01-01',
        {'Module': {ALPHA_TORSO: {'en': 'Pulls a target in.\nWeight used: 11\nArmor: 63,800\nShield: 29,000'}}},
        {ALPHA_TORSO: {'en': summary}},
    )


class TestMetaDescriptions:
    def test_get_falls_back_to_empty(self):
        assert meta('1').get('Pilot', KATE) == 'L1: Vanguard\nL2: Tactician'
        assert meta('1').get('Pilot', KATE, 'de') == 'Deutsch'

    def test_stat_summary_rows_and_flat_fields(self):
        summary = meta_with_stats().stat_summary(ALPHA_TORSO)
        assert summary.lead == 'Pulls a target in.'
        assert summary.rows == ((('Weight used', '11'), ('Armor', '63,800')), (('Shield', '29,000'),))
        assert summary.fields == (('Weight used', '11'), ('Armor', '63,800'), ('Shield', '29,000'))
        assert meta_with_stats().stat_summary(KATE) is None
        assert meta('1').stat_summary(ALPHA_TORSO) is None
        assert meta('1').get('Pilot', 'missing') == ''
        assert meta('1').get('Module', KATE) == ''

    def test_is_older_than(self):
        assert meta('5').is_older_than('6')
        assert not meta('6').is_older_than('6')
        assert not meta('7').is_older_than('6')  # a newer manual deploy is fine
        assert meta(None).is_older_than('6')


class TestStoreMetaRefresh:
    def test_load_fetches_once_without_a_recorded_deploy(self, data_dir, slug_map_file, deploy_state, monkeypatch):
        site = FakeSite(meta(None))
        store = make_store(data_dir, deploy_state, site, monkeypatch)
        assert site.calls == [None]
        assert store.snapshot.meta_descriptions.get('Pilot', KATE)
        assert store.refresh_if_changed() is False
        assert site.calls == [None]

    def test_new_deploy_refetches_once(self, data_dir, slug_map_file, deploy_state, monkeypatch):
        record_deploy(deploy_state, '10')
        site = FakeSite(meta('10'))
        store = make_store(data_dir, deploy_state, site, monkeypatch)
        objects = store.snapshot.objects
        assert store.refresh_if_changed() is False

        record_deploy(deploy_state, '11')
        site.served = meta('11', kate='L1: New')
        assert store.refresh_if_changed() is True
        assert site.calls == ['10', '11']
        assert store.snapshot.meta_descriptions.get('Pilot', KATE) == 'L1: New'
        assert store.snapshot.site_deploy.run_id == '11'
        assert store.snapshot.site_deploy.short_commit == 'abcdef1'
        assert store.snapshot.objects is objects
        assert store.refresh_if_changed() is False
        assert site.calls == ['10', '11']

    def test_stale_site_keeps_previous_and_retries(self, data_dir, slug_map_file, deploy_state, monkeypatch):
        record_deploy(deploy_state, '10')
        site = FakeSite(meta('10'))
        store = make_store(data_dir, deploy_state, site, monkeypatch)
        record_deploy(deploy_state, '11')
        site.served = meta('10', kate='stale')
        assert store.refresh_if_changed() is False
        assert store.snapshot.meta_descriptions.build_id == '10'
        assert store.snapshot.site_deploy.run_id == '10'
        site.served = meta('11', kate='fresh')
        assert store.refresh_if_changed() is True
        assert store.snapshot.meta_descriptions.get('Pilot', KATE) == 'fresh'

    def test_unreadable_deploy_state_keeps_previous(self, data_dir, slug_map_file, deploy_state, monkeypatch):
        record_deploy(deploy_state, '10')
        site = FakeSite(meta('10'))
        store = make_store(data_dir, deploy_state, site, monkeypatch)
        deploy_state.write_text('{"run_id": "11"}')  # no data_commit
        assert store.refresh_if_changed() is False
        assert store.snapshot.site_deploy.run_id == '10'

    def test_site_on_other_data_version_warns(self, data_dir, slug_map_file, deploy_state, monkeypatch):
        deploy_state.write_text(json.dumps(deploy_doc('10', data_version='2025-12-01')))
        warnings = []
        monkeypatch.setattr(store_module.logger, 'warning', warnings.append)
        make_store(data_dir, deploy_state, FakeSite(meta('10')), monkeypatch)
        assert any('2025-12-01' in w and '2026-01-01' in w for w in warnings)

    def test_unreachable_site_still_loads(self, data_dir, slug_map_file, deploy_state, monkeypatch):
        site = FakeSite(MetaDescriptionsError('down'))
        store = make_store(data_dir, deploy_state, site, monkeypatch)
        assert store.snapshot.meta_descriptions.descriptions == {}

    def test_without_deploy_state_fetches_only_at_startup(self, data_dir, slug_map_file, monkeypatch):
        site = FakeSite(meta('10'))
        store = make_store(data_dir, None, site, monkeypatch)
        assert store.refresh_if_changed() is False
        assert site.calls == [None]


class TestEmbedDescriptions:
    def test_meta_description_preferred_and_lines_kept(self, data_dir, slug_map_file, deploy_state, monkeypatch):
        store = make_store(data_dir, deploy_state, FakeSite(meta('1')), monkeypatch)
        index = LookupIndex.from_snapshot(store.snapshot)
        assert index.resolve('Kate Sinclair').entry.description == 'L1: Vanguard\nL2: Tactician'
        # No meta description: the object's own description, as before.
        assert index.resolve('Scourge').entry.description == 'Sustains a focused beam.'

    def test_stats_become_fields_and_leave_the_description(self, data_dir, slug_map_file, deploy_state, monkeypatch):
        store = make_store(data_dir, deploy_state, FakeSite(meta_with_stats()), monkeypatch)
        entry = LookupIndex.from_snapshot(store.snapshot).resolve('Alpha').entry.torso
        assert entry.description == 'Pulls a target in.'
        assert entry.stat_fields == (('Weight used', '11'), ('Armor', '63,800'), ('Shield', '29,000'))
