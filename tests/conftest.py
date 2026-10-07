"""A tiny WRFrontiersDB-Data clone, with its index/ (slug map and names), for tests."""

import json
from pathlib import Path

import pytest

from wrfdb_bot.services.lookup.index import LookupIndex
from wrfdb_bot.wrf_data import meta_descriptions
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.meta_descriptions import MetaDescriptions
from wrfdb_bot.wrf_data.object_types import OBJECT_TYPES
from wrfdb_bot.wrf_data.store import DataStore

SITE_URL = 'https://wrf-db.example'
SCOURGE_ICON_PATH = '/WRFrontiers/Content/Sparrow/UI/Textures/Modules/T_Module_Weapon_Scourge'


def en(text: str) -> dict:
    return {'Key': text, 'TableNamespace': 'Test', 'en': text}


OBJECTS = {
    'VirtualBot': {
        'alpha': {'id': 'alpha', 'name': en('Alpha')},
        'relic-alpha': {'id': 'relic-alpha', 'name': en('Relic Alpha')},
    },
    'Pilot': {
        'DA_Pilot_Rare_KateSinclair.0': {
            'first_name': en('Kate'),
            'last_name': en('Sinclair'),
            'bio': en('A Mayflower pilot.'),
        },
        'DA_Pilot_Common3.0': {'first_name': en('Vanguard'), 'bio': en('Tortuga pilot.')},
        'DA_Pilot_Common1.0': {'first_name': en('"Hammer" Petrova')},
        'DA_Pilot_Common35.0': {'first_name': en('Marcus Davis')},
        'DA_Pilot_Rare_MarcusShedd.0': {'first_name': en('Marcus'), 'second_name': en('Shedd')},
    },
    'Module': {
        'DA_Module_Weapon_Scourge.0': {
            'production_status': 'Ready',
            'name': en('Scourge'),
            'inventory_icon_path': SCOURGE_ICON_PATH,
            'description': en('Sustains a focused beam.'),
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
        'DA_Module_TorsoAlpha.0': {
            'production_status': 'Ready',
            'name': en('Alpha'),
            'description': en('Pulls a target in.'),
            'module_group_ref': 'OBJID_ModuleGroup::titan-torsos',
            'module_type_ref': 'OBJID_ModuleType::DA_ModuleType_TitanAlphaTorso.0',
            'virtual_bot_ref': 'OBJID_VirtualBot::alpha',
        },
        'DA_Module_ShoulderRelicAlpha01.0': {
            'production_status': 'Ready',
            'name': en('Relic Alpha Mk. II'),
            'module_group_ref': 'OBJID_ModuleGroup::titan-shoulder',
            'virtual_bot_ref': 'OBJID_VirtualBot::relic-alpha',
        },
        'DA_Module_ShoulderRelicAlpha02.0': {
            'production_status': 'Ready',
            'name': en('Relic Alpha Mk. I'),
            'module_group_ref': 'OBJID_ModuleGroup::titan-shoulder',
            'virtual_bot_ref': 'OBJID_VirtualBot::relic-alpha',
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
        'titan-torsos': {'name': en('Titan Torso')},
    },
}

SLUG_MAP = {
    'DA_Pilot_Rare_KateSinclair.0': 'kate-sinclair',
    'DA_Pilot_Common3.0': 'vanguard',
    'DA_Pilot_Common1.0': 'hammer-petrova',
    'DA_Pilot_Common35.0': 'marcus-davis',
    'DA_Pilot_Rare_MarcusShedd.0': 'marcus-shedd',
    'DA_Module_Weapon_Scourge.0': 'light-weapon-scourge',
    'DA_Module_ChassisAlpha.1': 'titan-chassis-alpha',
    'DA_Module_ShoulderLAlpha.0': 'titan-shoulder-left-alpha',
    'DA_Module_ShoulderRAlpha.0': 'titan-shoulder-right-alpha',
    'DA_Module_TorsoAlpha.0': 'titan-torsos-alpha',
    'DA_Module_Weapon_Railgun.0': 'light-weapon-railgun',
    'DA_Module_Weapon_GunNut.0': 'light-weapon-gun-nut',
    'DA_Talent_Leader1.0': 'vanguard',
    'DA_CharacterClass_Assault.0': 'assault',
    'DA_Class_Brawler.0': 'assault',
    'light-weapon': 'light-weapon',
    'titan-chassis': 'titan-chassis',
    'titan-shoulder': 'titan-shoulder',
    'alpha': 'alpha',
    # DA_Module_Unlinked.0 deliberately has no slug: it has no page.
}


NICKNAMES = {
    'DA_Pilot_Rare_KateSinclair.0': ['Kate'],
    'DA_Pilot_Common1.0': ['Hammer'],
    'DA_Pilot_Rare_MarcusShedd.0': ['Marcus'],
    'DA_Module_ChassisAlpha.1': ['Alpha Legs'],
}

ALIASES = {
    'DA_Module_ChassisAlpha.1': ['Alpha Chassis'],
    'DA_Module_ShoulderLAlpha.0': ['Alpha Shoulder Left', 'Alpha Left Shoulder'],
    'DA_Module_ShoulderRAlpha.0': ['Alpha Shoulder Right', 'Alpha Right Shoulder'],
    'DA_Module_TorsoAlpha.0': ['Alpha Torso'],
    'DA_Module_ShoulderRelicAlpha01.0': ['Relic Alpha Shoulder Mk. II', 'Relic Alpha Shoulder'],
    'DA_Module_ShoulderRelicAlpha02.0': ['Relic Alpha Shoulder Mk. I'],
}

# `vanguard` is a real name too: an abbreviation must never hide one.
ABBREVIATIONS = {'r': 'relic', 'alp': 'alpha', '2': 'mk ii', 'mk 2': 'mk ii', 'mk2': 'mk ii', 'vanguard': 'scourge'}


def write_data_dir(root: Path, version: str = '2026-01-01', objects: dict = OBJECTS) -> Path:
    objects_dir = root / 'current' / 'Objects'
    objects_dir.mkdir(parents=True, exist_ok=True)
    (root / 'current' / 'version.txt').write_text(version + '\n')
    for object_type in OBJECT_TYPES:
        (objects_dir / f'{object_type.name}.json').write_text(json.dumps(objects.get(object_type.name, {})))
    icon = root / 'textures' / (SCOURGE_ICON_PATH.lstrip('/') + '.png')
    icon.parent.mkdir(parents=True, exist_ok=True)
    icon.write_bytes(b'png')
    return root


def write_slug_map(data_dir: Path, slug_map: dict | None = None) -> Path:
    path = data_dir / 'index' / 'slug_map.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SLUG_MAP if slug_map is None else slug_map))
    return path


def write_nicknames(data_dir: Path, nicknames: dict | None = None) -> Path:
    path = data_dir / 'index' / 'nicknames.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(NICKNAMES if nicknames is None else nicknames))
    return path


def write_aliases(data_dir: Path, aliases: dict | None = None) -> Path:
    path = data_dir / 'index' / 'aliases.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ALIASES if aliases is None else aliases))
    return path


def write_abbreviations(data_dir: Path, abbreviations: dict | None = None) -> Path:
    path = data_dir / 'index' / 'abbreviations.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ABBREVIATIONS if abbreviations is None else abbreviations))
    return path


@pytest.fixture(autouse=True)
def no_site_fetch(monkeypatch):
    """Tests never reach the network: the Site serves no meta descriptions unless a test says so."""
    monkeypatch.setattr(meta_descriptions, 'fetch', lambda site_url, run_id: MetaDescriptions())


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return write_data_dir(tmp_path / 'data')


@pytest.fixture
def slug_map_file(data_dir: Path) -> Path:
    return write_slug_map(data_dir)


@pytest.fixture
def nicknames_file(data_dir: Path) -> Path:
    return write_nicknames(data_dir)


@pytest.fixture
def aliases_file(data_dir: Path) -> Path:
    return write_aliases(data_dir)


@pytest.fixture
def abbreviations_file(data_dir: Path) -> Path:
    return write_abbreviations(data_dir)


@pytest.fixture
def store(
    data_dir: Path, slug_map_file: Path, nicknames_file: Path, aliases_file: Path, abbreviations_file: Path
) -> DataStore:
    store = DataStore(DataRepo(data_dir), SITE_URL)
    store.load()
    return store


@pytest.fixture
def index(store: DataStore) -> LookupIndex:
    return LookupIndex.from_snapshot(store.snapshot)
