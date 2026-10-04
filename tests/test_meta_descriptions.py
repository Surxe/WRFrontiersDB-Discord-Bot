import json

import pytest
from conftest import SITE_URL

from wrfdb_bot.services.lookup.index import LookupIndex
from wrfdb_bot.wrf_data import meta_descriptions
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.meta_descriptions import MetaDescriptions, MetaDescriptionsError
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
    path.write_text(json.dumps({'site_run_id': run_id, 'game_version': '2026-01-01'}))


def make_store(data_dir, deploy_state, site: FakeSite, monkeypatch) -> DataStore:
    monkeypatch.setattr(meta_descriptions, 'fetch', site)
    store = DataStore(DataRepo(data_dir), SITE_URL, deploy_state)
    store.load()
    return store


class TestMetaDescriptions:
    def test_get_falls_back_to_empty(self):
        assert meta('1').get('Pilot', KATE) == 'L1: Vanguard\nL2: Tactician'
        assert meta('1').get('Pilot', KATE, 'de') == 'Deutsch'
        assert meta('1').get('Pilot', 'missing') == ''
        assert meta('1').get('Module', KATE) == ''

    def test_is_older_than(self):
        assert meta('5').is_older_than('6')
        assert not meta('6').is_older_than('6')
        assert not meta('7').is_older_than('6')  # a newer manual deploy is fine
        assert meta(None).is_older_than('6')

    def test_read_deployed_run_id(self, deploy_state):
        assert meta_descriptions.read_deployed_run_id(deploy_state) is None
        record_deploy(deploy_state, '42')
        assert meta_descriptions.read_deployed_run_id(deploy_state) == '42'
        deploy_state.write_text('{"site_run_id": null}')
        with pytest.raises(MetaDescriptionsError):
            meta_descriptions.read_deployed_run_id(deploy_state)


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
        site.served = meta('11', kate='fresh')
        assert store.refresh_if_changed() is True
        assert store.snapshot.meta_descriptions.get('Pilot', KATE) == 'fresh'

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
