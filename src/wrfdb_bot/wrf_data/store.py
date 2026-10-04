"""The current WRF data, shared by all services, refreshed when it changes."""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from . import meta_descriptions
from .data_repo import DataRepo
from .meta_descriptions import MetaDescriptions, MetaDescriptionsError
from .object_types import OBJECT_TYPES
from .site import SiteLinks, SlugMap


@dataclass(frozen=True)
class DataSnapshot:
    """One consistent view of the data. Replaced as a whole on refresh, never mutated."""

    version: str
    objects: dict[str, dict[str, dict]]
    """Object type name -> id -> object."""
    site_links: SiteLinks
    meta_descriptions: MetaDescriptions


class DataStore:
    """Holds the current DataSnapshot. The load/refresh methods block (file and network IO)."""

    def __init__(self, data_repo: DataRepo, site_url: str, site_deploy_state: Path | None = None):
        self.data_repo = data_repo
        self.site_url = site_url
        self.site_deploy_state = site_deploy_state
        """The pipeline's Site deploy record; meta descriptions are re-fetched when it changes."""
        self._snapshot: DataSnapshot | None = None

    @property
    def snapshot(self) -> DataSnapshot:
        if self._snapshot is None:
            raise RuntimeError('DataStore.load() has not run yet')
        return self._snapshot

    def load(self) -> DataSnapshot:
        """Load everything. Fails if the data repo can't be read; a missing slug map or
        unreachable Site only warns."""
        slug_map = self._fetch_slug_map(fallback={})
        meta = self._refresh_meta(MetaDescriptions(), startup=True)
        self._snapshot = self._build_snapshot(self.data_repo.read_version(), slug_map, meta)
        logger.info(
            f'Loaded data version {self._snapshot.version} '
            f'({sum(len(o) for o in self._snapshot.objects.values())} objects, {len(slug_map)} slugs, '
            f'meta descriptions from Site build {meta.build_id})'
        )
        return self._snapshot

    def refresh_if_changed(self) -> bool:
        """Reload if the data version, the slug map or the deployed Site changed. Returns whether it did."""
        current = self.snapshot
        version = self.data_repo.read_version()
        slug_map = self._fetch_slug_map(fallback=current.site_links.slug_map)
        meta = self._refresh_meta(current.meta_descriptions)
        if (
            version == current.version
            and slug_map == current.site_links.slug_map
            and meta is current.meta_descriptions
        ):
            return False
        if version == current.version:
            # The slug map / Site changed after current/ was pushed; keep the parsed objects.
            self._snapshot = DataSnapshot(version, current.objects, SiteLinks(self.site_url, slug_map), meta)
        else:
            self._snapshot = self._build_snapshot(version, slug_map, meta)
        logger.info(
            f'Refreshed data: version {current.version} -> {version}, {len(slug_map)} slugs, '
            f'meta descriptions from Site build {meta.build_id}'
        )
        return True

    def _build_snapshot(self, version: str, slug_map: SlugMap, meta: MetaDescriptions) -> DataSnapshot:
        objects = {t.name: self.data_repo.read_objects(t.name) for t in OBJECT_TYPES}
        return DataSnapshot(version, objects, SiteLinks(self.site_url, slug_map), meta)

    def _fetch_slug_map(self, fallback: SlugMap) -> SlugMap:
        try:
            return self.data_repo.read_slug_map()
        except (OSError, ValueError) as e:
            logger.warning(f'Could not read the slug map {self.data_repo.slug_map_file}: {e}; links may be missing')
            return fallback

    def _refresh_meta(self, current: MetaDescriptions, startup: bool = False) -> MetaDescriptions:
        """Fetch the Site's meta descriptions at startup and after each new deploy.

        Returns `current` itself when nothing new was taken.
        """
        try:
            run_id = meta_descriptions.read_deployed_run_id(self.site_deploy_state) if self.site_deploy_state else None
        except MetaDescriptionsError as e:
            logger.warning(f'{e}; meta descriptions not refreshed')
            return current
        if not startup and (run_id is None or not current.is_older_than(run_id)):
            return current
        try:
            fetched = meta_descriptions.fetch(self.site_url, run_id)
        except MetaDescriptionsError as e:
            logger.warning(f'{e}; embeds keep their previous descriptions')
            return current
        if run_id is not None and fetched.is_older_than(run_id):
            logger.warning(
                f'The Site still serves meta descriptions from build {fetched.build_id}, not the '
                f'deployed run {run_id}; retrying on the next refresh'
            )
            return fetched if not current.descriptions else current
        return fetched
