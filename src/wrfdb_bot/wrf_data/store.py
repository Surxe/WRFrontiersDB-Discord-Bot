"""The current WRF data, shared by all services, refreshed when it changes."""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from . import deploys, meta_descriptions
from .data_repo import DataRepo
from .deploys import DeployError, DeployRecord
from .meta_descriptions import MetaDescriptions, MetaDescriptionsError
from .object_types import OBJECT_TYPES
from .site import SiteLinks, SlugMap

Nicknames = dict[str, list[str]]


@dataclass(frozen=True)
class DataSnapshot:
    """One consistent view of the data. Replaced as a whole on refresh, never mutated."""

    version: str
    objects: dict[str, dict[str, dict]]
    """Object type name -> id -> object."""
    site_links: SiteLinks
    meta_descriptions: MetaDescriptions
    nicknames: Nicknames
    """Object id -> nicknames, from Data's `index/nicknames.json`."""
    site_deploy: DeployRecord | None = None
    """The recorded Site deploy the meta descriptions came from (its Data commit), if known."""


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
        """Load everything. Fails if the data repo can't be read; a missing slug map,
        nicknames file or unreachable Site only warns."""
        slug_map = self._fetch_slug_map(fallback={})
        nicknames = self._fetch_nicknames(fallback={})
        meta, deploy = self._refresh_site(MetaDescriptions(), None, startup=True)
        self._snapshot = self._build_snapshot(self.data_repo.read_version(), slug_map, meta, deploy, nicknames)
        logger.info(
            f'Loaded data version {self._snapshot.version} '
            f'({sum(len(o) for o in self._snapshot.objects.values())} objects, {len(slug_map)} slugs, '
            f'{len(nicknames)} nicknamed, '
            f'meta descriptions from Site build {meta.build_id}{_site_data(deploy)})'
        )
        self._warn_if_site_differs(self._snapshot)
        return self._snapshot

    def refresh_if_changed(self) -> bool:
        """Reload if the data version, index/ or the deployed Site changed. Returns whether it did."""
        current = self.snapshot
        version = self.data_repo.read_version()
        slug_map = self._fetch_slug_map(fallback=current.site_links.slug_map)
        nicknames = self._fetch_nicknames(fallback=current.nicknames)
        meta, deploy = self._refresh_site(current.meta_descriptions, current.site_deploy)
        if (
            version == current.version
            and slug_map == current.site_links.slug_map
            and nicknames == current.nicknames
            and meta is current.meta_descriptions
        ):
            return False
        if version == current.version:
            # index/ / the Site changed after current/ was pushed; keep the parsed objects.
            self._snapshot = DataSnapshot(
                version, current.objects, SiteLinks(self.site_url, slug_map), meta, nicknames, deploy
            )
        else:
            self._snapshot = self._build_snapshot(version, slug_map, meta, deploy, nicknames)
        logger.info(
            f'Refreshed data: version {current.version} -> {version}, {len(slug_map)} slugs, '
            f'meta descriptions from Site build {meta.build_id}{_site_data(deploy)}'
        )
        self._warn_if_site_differs(self._snapshot)
        return True

    def _build_snapshot(
        self,
        version: str,
        slug_map: SlugMap,
        meta: MetaDescriptions,
        deploy: DeployRecord | None,
        nicknames: Nicknames,
    ) -> DataSnapshot:
        objects = {t.name: self.data_repo.read_objects(t.name) for t in OBJECT_TYPES}
        return DataSnapshot(version, objects, SiteLinks(self.site_url, slug_map), meta, nicknames, deploy)

    @staticmethod
    def _warn_if_site_differs(snapshot: DataSnapshot) -> None:
        deploy = snapshot.site_deploy
        if deploy is not None and deploy.data_version != snapshot.version:
            logger.warning(
                f'The Site was built from data version {deploy.data_version} ({deploy.short_commit}), '
                f'but DATA_DIR has {snapshot.version}; the Site lags until its next deploy'
            )

    def _fetch_slug_map(self, fallback: SlugMap) -> SlugMap:
        try:
            return self.data_repo.read_slug_map()
        except (OSError, ValueError) as e:
            logger.warning(f'Could not read the slug map {self.data_repo.slug_map_file}: {e}; links may be missing')
            return fallback

    def _fetch_nicknames(self, fallback: Nicknames) -> Nicknames:
        try:
            return self.data_repo.read_nicknames()
        except (OSError, ValueError) as e:
            logger.warning(f'Could not read the nicknames {self.data_repo.nicknames_file}: {e}; lookups use full names')
            return fallback

    def _refresh_site(
        self, current: MetaDescriptions, current_deploy: DeployRecord | None, startup: bool = False
    ) -> tuple[MetaDescriptions, DeployRecord | None]:
        """Fetch the Site's meta descriptions at startup and after each new recorded deploy.

        Returns them with the deploy they came from; `current` itself (and `current_deploy`)
        when nothing new was taken.
        """
        try:
            deploy = deploys.read_state(self.site_deploy_state) if self.site_deploy_state else None
        except DeployError as e:
            logger.warning(f'{e}; meta descriptions not refreshed')
            return current, current_deploy
        if not startup and (deploy is None or not current.is_older_than(deploy.run_id)):
            return current, current_deploy
        run_id = deploy.run_id if deploy else None
        try:
            fetched = meta_descriptions.fetch(self.site_url, run_id)
        except MetaDescriptionsError as e:
            logger.warning(f'{e}; embeds keep their previous descriptions')
            return current, current_deploy
        if run_id is not None and fetched.is_older_than(run_id):
            logger.warning(
                f'The Site still serves meta descriptions from build {fetched.build_id}, not the '
                f'deployed run {run_id}; retrying on the next refresh'
            )
            return (fetched, None) if not current.descriptions else (current, current_deploy)
        return fetched, deploy


def _site_data(deploy: DeployRecord | None) -> str:
    return f', Site data {deploy.short_commit} ({deploy.data_version})' if deploy else ''
