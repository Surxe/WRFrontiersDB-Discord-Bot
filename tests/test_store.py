import json

from conftest import OBJECTS, SITE_URL, write_data_dir

from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.store import DataStore


class TestDataStore:
    def test_refresh_unchanged(self, store):
        snapshot = store.snapshot
        assert store.refresh_if_changed() is False
        assert store.snapshot is snapshot

    def test_refresh_on_new_data_version(self, store, data_dir):
        objects = {**OBJECTS, 'Faction': {'DA_Faction_New.0': {'name': {'en': 'New'}}}}
        write_data_dir(data_dir, version='2026-02-02', objects=objects)
        assert store.refresh_if_changed() is True
        assert store.snapshot.version == '2026-02-02'
        assert 'DA_Faction_New.0' in store.snapshot.objects['Faction']

    def test_refresh_on_new_slug_only(self, store, slug_map_file):
        objects = store.snapshot.objects
        slug_map = json.loads(slug_map_file.read_text())
        slug_map['DA_Module_Unlinked.0'] = 'module-unlinked'
        slug_map_file.write_text(json.dumps(slug_map))
        assert store.refresh_if_changed() is True
        assert store.snapshot.objects is objects
        assert store.snapshot.site_links.slug_map['DA_Module_Unlinked.0'] == 'module-unlinked'

    def test_unreadable_slug_map_keeps_previous(self, store, slug_map_file):
        slug_map = store.snapshot.site_links.slug_map
        slug_map_file.write_text('not json')
        assert store.refresh_if_changed() is False
        assert store.snapshot.site_links.slug_map == slug_map

    def test_load_without_slug_map_still_works(self, data_dir):
        store = DataStore(DataRepo(data_dir), SITE_URL)
        snapshot = store.load()
        assert snapshot.site_links.slug_map == {}
