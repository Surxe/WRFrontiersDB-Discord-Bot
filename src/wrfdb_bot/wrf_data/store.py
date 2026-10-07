"""The current WRF data, shared by all services, refreshed when it changes."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from loguru import logger

from . import deploys, meta_descriptions
from .data_repo import DataRepo
from .deploys import DeployError, DeployRecord
from .meta_descriptions import MetaDescriptions, MetaDescriptionsError
from .object_types import OBJECT_TYPES
from .site import SiteLinks, SlugMap
from .textures import DEFAULT_DATA_RAW_URL, TextureLinks

Names = dict[str, list[str]]
"""Object id -> other names, as Data's `index/nicknames.json` and `index/aliases.json` hold them."""


@dataclass(frozen=True)
class LookupNames:
    """The other names objects answer to, from Data's `index/` (decided there, never by the bot)."""

    nicknames: Names = field(default_factory=dict)
    """Object id -> nicknames, from `index/nicknames.json`."""
    aliases: Names = field(default_factory=dict)
    """Object id -> aliases, from `index/aliases.json`."""
    abbreviations: dict[str, str] = field(default_factory=dict)
    """Short word -> full word(s), from `index/abbreviations.json`."""


@dataclass(frozen=True)
class DataSnapshot:
    """One consistent view of the data. Replaced as a whole on refresh, never mutated."""

    version: str
    objects: dict[str, dict[str, dict]]
    """Object type name -> id -> object."""
    site_links: SiteLinks
    meta_descriptions: MetaDescriptions
    names: LookupNames
    site_deploy: DeployRecord | None = None
    """The recorded Site deploy the meta descriptions came from (its Data commit), if known."""
    textures: TextureLinks | None = None
    """Icon links, pinned to the Data commit these objects were read at."""


class DataStore:
    """Holds the current DataSnapshot. The load/refresh methods block (file and network IO)."""

    def __init__(
        self,
        data_repo: DataRepo,
        site_url: str,
        site_deploy_state: Path | None = None,
        data_raw_url: str = DEFAULT_DATA_RAW_URL,
    ):
        self.data_repo = data_repo
        self.site_url = site_url
        self.data_raw_url = data_raw_url
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
        names file or unreachable Site only warns."""
        slug_map = self._fetch_slug_map(fallback={})
        names = self._fetch_names(fallback=LookupNames())
        meta, deploy = self._refresh_site(MetaDescriptions(), None, startup=True)
        self._snapshot = self._build_snapshot(self.data_repo.read_version(), slug_map, meta, deploy, names)
        logger.info(
            f'Loaded data version {self._snapshot.version} '
            f'({sum(len(o) for o in self._snapshot.objects.values())} objects, {len(slug_map)} slugs, '
            f'{len(names.nicknames)} nicknamed, {len(names.aliases)} aliased, '
            f'{len(names.abbreviations)} abbreviations, '
            f'meta descriptions from Site build {meta.build_id}{_site_data(deploy)})'
        )
        self._warn_if_site_differs(self._snapshot)
        return self._snapshot

    def refresh_if_changed(self) -> bool:
        """Reload if the data version, index/ or the deployed Site changed. Returns whether it did."""
        current = self.snapshot
        version = self.data_repo.read_version()
        slug_map = self._fetch_slug_map(fallback=current.site_links.slug_map)
        names = self._fetch_names(fallback=current.names)
        meta, deploy = self._refresh_site(current.meta_descriptions, current.site_deploy)
        textures = self._texture_links()
        if (
            version == current.version
            and slug_map == current.site_links.slug_map
            and names == current.names
            and meta is current.meta_descriptions
            and textures.commit == (current.textures.commit if current.textures else None)
        ):
            return False
        if version == current.version:
            # index/ / the Site changed after current/ was pushed; keep the parsed objects.
            self._snapshot = DataSnapshot(
                version, current.objects, SiteLinks(self.site_url, slug_map), meta, names, deploy, textures
            )
        else:
            self._snapshot = self._build_snapshot(version, slug_map, meta, deploy, names)
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
        names: LookupNames,
    ) -> DataSnapshot:
        objects = {t.name: self.data_repo.read_objects(t.name) for t in OBJECT_TYPES}
        return DataSnapshot(
            version, objects, SiteLinks(self.site_url, slug_map), meta, names, deploy, self._texture_links()
        )

    def _texture_links(self) -> TextureLinks:
        return TextureLinks(self.data_raw_url, self.data_repo.read_commit(), self.data_repo.textures_dir)

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

    def _fetch_names(self, fallback: LookupNames) -> LookupNames:
        """Each file read on its own: one that can't be read keeps its `fallback` part."""
        repo = self.data_repo
        return LookupNames(
            nicknames=_read_or(repo.read_nicknames, repo.nicknames_file, fallback.nicknames),
            aliases=_read_or(repo.read_aliases, repo.aliases_file, fallback.aliases),
            abbreviations=_read_or(repo.read_abbreviations, repo.abbreviations_file, fallback.abbreviations),
        )

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


T = TypeVar('T')


def _read_or(read: Callable[[], T], path: Path, fallback: T) -> T:
    try:
        return read()
    except (OSError, ValueError) as e:
        logger.warning(f'Could not read {path}: {e}; lookups use full names')
        return fallback


def _site_data(deploy: DeployRecord | None) -> str:
    return f', Site data {deploy.short_commit} ({deploy.data_version})' if deploy else ''
