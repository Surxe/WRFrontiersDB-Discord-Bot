"""A tiny WRFrontiersDB-Data clone and Site slug map for tests."""

import json
from pathlib import Path

import pytest

from wrfdb_bot.services.lookup.index import LookupIndex
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.object_types import OBJECT_TYPES
from wrfdb_bot.wrf_data.store import DataStore

SITE_URL = 'https://wrf-db.example'


def en(text: str) -> dict:
    return {'Key': text, 'TableNamespace': 'Test', 'en': text}


OBJECTS = {
    'VirtualBot': {
        'alpha': {'id': 'alpha', 'name': en('Alpha')},
    },
    'Pilot': {
        'DA_Pilot_Rare_KateSinclair.0': {
            'first_name': en('Kate'),
            'last_name': en('Sinclair'),
            'bio': en('A Mayflower pilot.'),
        },
        'DA_Pilot_Common3.0': {'first_name': en('Vanguard'), 'bio': en('Tortuga pilot.')},
        'DA_Pilot_Common1.0': {'first_name': en('"Hammer" Petrova')},
    },
    'Module': {
        'DA_Module_Weapon_Scourge.0': {
            'production_status': 'Ready',
            'name': en('Scourge'),
            'description': en('Sustains a <Highlight>focused</> beam.'),
            'module_group_ref': 'OBJID_ModuleGroup::light-weapon',
        },
        'DA_Module_Weapon_Secret.0': {'name': en('Secret Gun')},
        'DA_Module_ChassisAlpha.1': {
            'production_status': 'Ready',
            'name': en('Alpha'),
            'module_group_ref': 'OBJID_ModuleGroup::titan-chassis',
            'virtual_bot_ref': 'OBJID_VirtualBot::alpha',
        },
        'DA_Module_ShoulderLAlpha.0': {
            'production_status': 'Ready',
            'name': en('Alpha'),
            'module_group_ref': 'OBJID_ModuleGroup::titan-shoulder',
            'virtual_bot_ref': 'OBJID_VirtualBot::alpha',
            'shoulder_side': 'L',
        },
        'DA_Module_ShoulderRAlpha.0': {
            'production_status': 'Ready',
            'name': en('Alpha'),
            'module_group_ref': 'OBJID_ModuleGroup::titan-shoulder',
            'virtual_bot_ref': 'OBJID_VirtualBot::alpha',
            'shoulder_side': 'R',
        },
        'DA_Module_Unlinked.0': {'production_status': 'Ready', 'name': en('Unlinked')},
        'DA_Module_Weapon_Railgun.0': {'production_status': 'Ready', 'name': en('Railgun')},
        'DA_Module_Weapon_GunNut.0': {'production_status': 'Ready', 'name': en('Gun Nut')},
    },
    'PilotTalent': {
        'DA_Talent_Leader1.0': {'name': en('Vanguard'), 'description': en('Boosts allies by {Boost}.')},
    },
    'CharacterClass': {'DA_CharacterClass_Assault.0': {'name': en('Assault')}},
    'PilotClass': {'DA_Class_Brawler.0': {'name': en('Assault')}},
    'ModuleGroup': {
        'light-weapon': {'name': en('Light Weapon')},
        'titan-chassis': {'name': en('Titan Chassis')},
        'titan-shoulder': {'name': en('Titan Shoulder')},
    },
}

SLUG_MAP = {
    'DA_Pilot_Rare_KateSinclair.0': 'kate-sinclair',
    'DA_Pilot_Common3.0': 'vanguard',
    'DA_Pilot_Common1.0': 'hammer-petrova',
    'DA_Module_Weapon_Scourge.0': 'light-weapon-scourge',
    'DA_Module_ChassisAlpha.1': 'titan-chassis-alpha',
    'DA_Module_ShoulderLAlpha.0': 'titan-shoulder-left-alpha',
    'DA_Module_ShoulderRAlpha.0': 'titan-shoulder-right-alpha',
    'DA_Module_Weapon_Railgun.0': 'light-weapon-railgun',
    'DA_Module_Weapon_GunNut.0': 'light-weapon-gun-nut',
    'DA_Talent_Leader1.0': 'vanguard',
    'DA_CharacterClass_Assault.0': 'assault',
    'DA_Class_Brawler.0': 'assault',
    'light-weapon': 'light-weapon',
    'titan-chassis': 'titan-chassis',
    'titan-shoulder': 'titan-shoulder',
    # DA_Module_Unlinked.0 deliberately has no slug: Data is ahead of the Site.
}


def write_data_dir(root: Path, version: str = '2026-01-01', objects: dict = OBJECTS) -> Path:
    objects_dir = root / 'current' / 'Objects'
    objects_dir.mkdir(parents=True, exist_ok=True)
    (root / 'current' / 'version.txt').write_text(version + '\n')
    for object_type in OBJECT_TYPES:
        (objects_dir / f'{object_type.name}.json').write_text(json.dumps(objects.get(object_type.name, {})))
    return root


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return write_data_dir(tmp_path / 'data')


@pytest.fixture
def slug_map_file(tmp_path: Path) -> Path:
    path = tmp_path / 'slug_map.json'
    path.write_text(json.dumps(SLUG_MAP))
    return path


@pytest.fixture
def store(data_dir: Path, slug_map_file: Path) -> DataStore:
    store = DataStore(DataRepo(data_dir), SITE_URL, str(slug_map_file))
    store.load()
    return store


@pytest.fixture
def index(store: DataStore) -> LookupIndex:
    return LookupIndex.from_snapshot(store.snapshot)
