"""The current WRF data, shared by all services, refreshed when it changes."""

from dataclasses import dataclass

from loguru import logger

from .data_repo import DataRepo
from .object_types import OBJECT_TYPES
from .site import SiteLinks, SlugMap


@dataclass(frozen=True)
class DataSnapshot:
    """One consistent view of the data. Replaced as a whole on refresh, never mutated."""

    version: str
    objects: dict[str, dict[str, dict]]
    """Object type name -> id -> object."""
    site_links: SiteLinks


class DataStore:
    """Holds the current DataSnapshot. The load/refresh methods block (file IO)."""

    def __init__(self, data_repo: DataRepo, site_url: str):
        self.data_repo = data_repo
        self.site_url = site_url
        self._snapshot: DataSnapshot | None = None

    @property
    def snapshot(self) -> DataSnapshot:
        if self._snapshot is None:
            raise RuntimeError('DataStore.load() has not run yet')
        return self._snapshot

    def load(self) -> DataSnapshot:
        """Load everything. Fails if the data repo can't be read; a missing slug map only warns."""
        slug_map = self._fetch_slug_map(fallback={})
        self._snapshot = self._build_snapshot(self.data_repo.read_version(), slug_map)
        logger.info(
            f'Loaded data version {self._snapshot.version} '
            f'({sum(len(o) for o in self._snapshot.objects.values())} objects, {len(slug_map)} slugs)'
        )
        return self._snapshot

    def refresh_if_changed(self) -> bool:
        """Reload if the data version or the slug map changed. Returns whether it did."""
        current = self.snapshot
        version = self.data_repo.read_version()
        slug_map = self._fetch_slug_map(fallback=current.site_links.slug_map)
        if version == current.version and slug_map == current.site_links.slug_map:
            return False
        if version == current.version:
            # Only the slug map changed (it is pushed after current/); keep the parsed objects.
            self._snapshot = DataSnapshot(version, current.objects, SiteLinks(self.site_url, slug_map))
        else:
            self._snapshot = self._build_snapshot(version, slug_map)
        logger.info(f'Refreshed data: version {current.version} -> {version}, {len(slug_map)} slugs')
        return True

    def _build_snapshot(self, version: str, slug_map: SlugMap) -> DataSnapshot:
        objects = {t.name: self.data_repo.read_objects(t.name) for t in OBJECT_TYPES}
        return DataSnapshot(version, objects, SiteLinks(self.site_url, slug_map))

    def _fetch_slug_map(self, fallback: SlugMap) -> SlugMap:
        try:
            return self.data_repo.read_slug_map()
        except (OSError, ValueError) as e:
            logger.warning(f'Could not read the slug map {self.data_repo.slug_map_file}: {e}; links may be missing')
            return fallback
