"""Options from environment variables (and `.env`, loaded by the caller). See `.env.example`."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SITE_URL = 'https://wrf-db.info'
DEFAULT_VISUALIZER_URL = 'https://surxe.github.io/WRFrontiers-Discount-Visualizer'
DEFAULT_ENABLED_SERVICES = ('lookup',)
DEFAULT_DATA_REFRESH_MINUTES = 10.0
DEFAULT_LOG_LEVEL = 'INFO'


@dataclass(frozen=True)
class DataOptions:
    data_dir: Path
    site_url: str
    site_deploy_state: Path | None
    visualizer_url: str
    data_refresh_minutes: float


@dataclass(frozen=True)
class Options:
    discord_bot_token: str
    guild_ids: tuple[int, ...]
    enabled_services: tuple[str, ...]
    data: DataOptions
    log_level: str


def load_data_options() -> DataOptions:
    data_dir = _required('DATA_DIR')
    site_url = _optional('SITE_URL', DEFAULT_SITE_URL).rstrip('/')
    site_deploy_state = os.environ.get('SITE_DEPLOY_STATE', '').strip()
    return DataOptions(
        data_dir=Path(data_dir),
        site_url=site_url,
        site_deploy_state=Path(site_deploy_state) if site_deploy_state else None,
        visualizer_url=_optional('VISUALIZER_URL', DEFAULT_VISUALIZER_URL).rstrip('/'),
        data_refresh_minutes=float(_optional('DATA_REFRESH_MINUTES', str(DEFAULT_DATA_REFRESH_MINUTES))),
    )


def load_options() -> Options:
    return Options(
        discord_bot_token=_required('DISCORD_BOT_TOKEN'),
        guild_ids=tuple(int(g) for g in _list('GUILD_IDS')),
        enabled_services=_list('ENABLED_SERVICES') or DEFAULT_ENABLED_SERVICES,
        data=load_data_options(),
        log_level=_optional('LOG_LEVEL', DEFAULT_LOG_LEVEL).upper(),
    )


def _optional(name: str, default: str) -> str:
    return os.environ.get(name, '').strip() or default


def _required(name: str) -> str:
    value = os.environ.get(name, '').strip()
    if not value:
        raise ValueError(f'Missing {name}. Set it in the environment or .env (see .env.example).')
    return value


def _list(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.environ.get(name, '').split(',') if item.strip())
