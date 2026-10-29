"""A file the bot touches while connected to Discord, so an outside check can tell when it last was."""

from pathlib import Path

from loguru import logger


def touch_heartbeat(path: Path) -> None:
    try:
        path.touch()
    except OSError as exc:
        logger.warning(f'Could not touch HEARTBEAT_FILE {path}: {exc}')
