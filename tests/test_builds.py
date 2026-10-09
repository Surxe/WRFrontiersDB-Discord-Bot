"""The builds service: `/models` build-code links, read with WRFrontiersDB-Data's codec.

The codec is Data's own file (`tools/wrfdb_data/build_code.py`), taken from a Data clone:
`WRFDB_DATA_DIR`, else the sibling checkout `../WRFrontiersDB-Data`. Without one these
tests are skipped.
"""

import json
import os
import shutil
from pathlib import Path

import pytest
from conftest import SITE_URL

from wrfdb_bot.services.builds.embeds import build_embed, reply_kwargs
from wrfdb_bot.services.builds.links import find_codes, models_url, parse_build_arg, read_link
from wrfdb_bot.wrf_data.build_codes import CODEC_REL, BuildCodes, load_codec_module
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.store import DataStore

DATA_CLONE = Path(os.environ.get('WRFDB_DATA_DIR', Path(__file__).resolve().parents[2] / 'WRFrontiersDB-Data'))
needs_data = pytest.mark.skipif(not (DATA_CLONE / CODEC_REL).exists(), reason=f'no Data clone at {DATA_CLONE}')

CHASSIS = 'DA_Module_ChassisAlpha.1'
TORSO = 'DA_Module_TorsoAlpha.0'
LEFT = 'DA_Module_ShoulderLAlpha.0'
RIGHT = 'DA_Module_ShoulderRAlpha.0'
RAILGUN = 'DA_Module_Weapon_Railgun.0'

# The conftest titan: chassis -> torso -> two shoulders; the left one has a weapon slot.
REGISTRY = {
    'format': 1,
    'root_socket': 'chassis',
    'sockets': {
        'chassis': {'required': True, 'candidates': [CHASSIS]},
        'T': {'required': True, 'candidates': [TORSO]},
        'SL': {'required': True, 'candidates': [LEFT]},
        'SR': {'required': True, 'candidates': [RIGHT]},
        'W': {'required': False, 'candidates': ['DA_Module_Weapon_Scourge.0', RAILGUN]},
    },
    'modules': {
        CHASSIS: {'sockets': [['Root', 'T']]},
        TORSO: {'sockets': [['Shoulder_L', 'SL'], ['Shoulder_R', 'SR']]},
        LEFT: {'sockets': [['Shoulder_Weapon_0', 'W']]},
        RIGHT: {'sockets': []},
        'DA_Module_Weapon_Scourge.0': {'sockets': []},
        RAILGUN: {'sockets': []},
    },
}
WITH_RAILGUN = '00020'  # chassis, torso, left shoulder, Railgun (position 2), right shoulder
NO_WEAPON = '00000'


def write_build_codes(data_dir: Path, registry: dict = REGISTRY) -> None:
    (data_dir / 'index').mkdir(parents=True, exist_ok=True)
    (data_dir / 'index' / 'build_codes.json').write_text(json.dumps(registry))
    codec = data_dir / CODEC_REL
    codec.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(DATA_CLONE / CODEC_REL, codec)


@pytest.fixture
def build_store(data_dir, slug_map_file, nicknames_file, aliases_file) -> DataStore:
    write_build_codes(data_dir)
    store = DataStore(DataRepo(data_dir), SITE_URL)
    store.load()
    return store


class TestFindCodes:
    def test_reads_a_and_b(self):
        text = f'look {SITE_URL}/models?lang=en&a=00020&b=00000&layout=side and'
        assert find_codes(text, SITE_URL) == [('00020', '00000')]

    def test_a_only_www_and_angle_brackets(self):
        host = SITE_URL.split('//')[1]
        text = f'<https://www.{host}/models?a=x-_> and https://{host}/models/?a=y'
        assert find_codes(text, SITE_URL) == [('x-_', None), ('y', None)]

    def test_ignores_links_without_a_and_other_sites(self):
        text = f'{SITE_URL}/models?chassis=X https://example.com/models?a=1 {SITE_URL}/pilots/?a=2'
        assert find_codes(text, SITE_URL) == []


class TestBuildArg:
    def test_one_code_two_codes_or_a_link(self):
        assert parse_build_arg(' 00020 ', SITE_URL) == ('00020', None)
        assert parse_build_arg('00020  00000', SITE_URL) == ('00020', '00000')
        assert parse_build_arg(f'{SITE_URL}/models?a=00020&b=00000', SITE_URL) == ('00020', '00000')

    def test_anything_else_is_none(self):
        assert parse_build_arg('', SITE_URL) is None
        assert parse_build_arg('a b c', SITE_URL) is None

    def test_models_url(self):
        assert models_url(SITE_URL + '/', '00020') == f'{SITE_URL}/models?a=00020'
        assert models_url(SITE_URL, 'x-_', '0') == f'{SITE_URL}/models?a=x-_&b=0'


@needs_data
class TestReadLink:
    def test_parts_named_and_linked(self, build_store):
        snapshot = build_store.snapshot
        link = read_link(snapshot, snapshot.build_codes, WITH_RAILGUN, NO_WEAPON)
        a, b = link.builds
        assert [(p.slot, p.name) for p in a] == [
            ('Chassis', 'Alpha Chassis'),
            ('Torso', 'Alpha Torso'),
            ('Left shoulder', 'Alpha Shoulder Left'),
            ('Left weapon 1', 'Railgun'),
            ('Right shoulder', 'Alpha Shoulder Right'),
        ]
        assert a[3].url == f'{SITE_URL}/modules/light-weapon-railgun/'
        assert 'Left weapon 1' not in [p.slot for p in b]

    def test_too_new_and_invalid(self, build_store):
        snapshot = build_store.snapshot
        assert read_link(snapshot, snapshot.build_codes, '1', None).too_new
        invalid = read_link(snapshot, snapshot.build_codes, WITH_RAILGUN, '*')
        assert invalid.invalid and not invalid.builds


@needs_data
class TestEmbeds:
    def test_build_embed_lists_parts_only(self, build_store):
        snapshot = build_store.snapshot
        embed = build_embed(read_link(snapshot, snapshot.build_codes, WITH_RAILGUN, NO_WEAPON), '2026-01-01')
        assert embed.title is None and embed.url is None
        assert embed.description.startswith('**Build A**\nChassis: [Alpha Chassis](')
        assert '**Build B**' in embed.description
        assert f'Left weapon 1: [Railgun]({SITE_URL}/modules/light-weapon-railgun/)' in embed.description
        assert embed.footer.text == 'Data 2026-01-01'

    def test_viewer_url_titles_the_embed(self, build_store):
        snapshot = build_store.snapshot
        url = models_url(SITE_URL, WITH_RAILGUN)
        embed = reply_kwargs([read_link(snapshot, snapshot.build_codes, WITH_RAILGUN, None)], '', url)['embeds'][0]
        assert embed.title == 'Open in the model viewer' and embed.url == url

    def test_single_build_and_problems(self, build_store):
        snapshot = build_store.snapshot
        links = [read_link(snapshot, snapshot.build_codes, c, None) for c in (WITH_RAILGUN, '1', '*')]
        kwargs = reply_kwargs(links, '2026-01-01')
        assert len(kwargs['embeds']) == 1
        assert kwargs['embeds'][0].description.startswith('**Build**\n')
        assert 'newer than the bot' in kwargs['content'] and "isn't a build code" in kwargs['content']
        assert '`_00`' in reply_kwargs([read_link(snapshot, snapshot.build_codes, '_00', None)])['content']


@needs_data
class TestStore:
    def test_loads_and_reloads_on_registry_change(self, build_store, data_dir):
        codes = build_store.snapshot.build_codes
        assert codes is not None
        assert codes.decode(WITH_RAILGUN)['Shoulder_L.Shoulder_Weapon_0'] == RAILGUN
        assert build_store.refresh_if_changed() is False
        grown = json.loads(json.dumps(REGISTRY))
        grown['sockets']['W']['candidates'].append('DA_Module_Weapon_GunNut.0')
        grown['modules']['DA_Module_Weapon_GunNut.0'] = {'sockets': []}
        write_build_codes(data_dir, grown)
        assert build_store.refresh_if_changed() is True
        assert build_store.snapshot.build_codes is not codes
        assert build_store.snapshot.build_codes.decode('00030')['Shoulder_L.Shoulder_Weapon_0'] == (
            'DA_Module_Weapon_GunNut.0'
        )

    def test_missing_registry_disables_codes(self, store):
        assert store.snapshot.build_codes is None


@needs_data
def test_data_vectors_decode():
    """Data's codec, loaded the way the bot loads it, reproduces Data's published vectors."""
    codes = BuildCodes(
        load_codec_module(DATA_CLONE),
        json.loads((DATA_CLONE / 'index' / 'build_codes.json').read_text()),
    )
    vectors = json.loads((DATA_CLONE / 'index' / 'build_code_vectors.json').read_text())
    for v in vectors['vectors']:
        assert codes.decode(v['code']) == v['build']
