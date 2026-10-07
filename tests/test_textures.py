from pathlib import Path

from conftest import SCOURGE_ICON_PATH, SITE_URL

from wrfdb_bot.services.lookup.embeds import reply_kwargs
from wrfdb_bot.services.lookup.index import LookupIndex
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.store import DataStore
from wrfdb_bot.wrf_data.textures import TextureLinks

RAW_URL = 'https://raw.example/Data'


def _textures(tmp_path: Path, commit: str | None = 'abc123') -> TextureLinks:
    icon = tmp_path / 'textures' / 'WRFrontiers' / 'T_Icon.png'
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b'png')
    return TextureLinks(RAW_URL + '/', commit, tmp_path / 'textures')


class TestTextureLinks:
    def test_url_is_pinned_to_the_commit(self, tmp_path):
        assert _textures(tmp_path).url('/WRFrontiers/T_Icon') == f'{RAW_URL}/abc123/textures/WRFrontiers/T_Icon.png'

    def test_no_url_without_path_commit_or_file(self, tmp_path):
        textures = _textures(tmp_path)
        assert textures.url(None) is None
        assert textures.url('/WRFrontiers/T_Missing') is None
        assert TextureLinks(RAW_URL, None, textures.textures_dir).url('/WRFrontiers/T_Icon') is None


class TestIconThumbnail:
    def _index(self, data_dir, monkeypatch, commit):
        monkeypatch.setattr(DataRepo, 'read_commit', lambda self: commit)
        store = DataStore(DataRepo(data_dir), SITE_URL, data_raw_url=RAW_URL)
        return LookupIndex.from_snapshot(store.load())

    def test_embed_shows_the_icon_from_data(self, data_dir, slug_map_file, monkeypatch):
        index = self._index(data_dir, monkeypatch, 'abc123')
        embed = reply_kwargs([index.resolve('Scourge')])['embeds'][0]
        assert embed.thumbnail.url == f'{RAW_URL}/abc123/textures{SCOURGE_ICON_PATH}.png'

    def test_no_thumbnail_without_icon_or_commit(self, data_dir, slug_map_file, monkeypatch):
        index = self._index(data_dir, monkeypatch, 'abc123')
        assert reply_kwargs([index.resolve('Railgun')])['embeds'][0].thumbnail.url is None
        index = self._index(data_dir, monkeypatch, None)
        assert reply_kwargs([index.resolve('Scourge')])['embeds'][0].thumbnail.url is None
