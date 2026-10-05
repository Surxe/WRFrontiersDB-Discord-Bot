"""What /about reports: the bot's data, and which Data commit each frontend serves.

Discord-free, so it stays testable; `cog.py` turns a Status into an embed.
"""

from dataclasses import dataclass

from wrfdb_bot.wrf_data import deploys
from wrfdb_bot.wrf_data.data_repo import DataRepo
from wrfdb_bot.wrf_data.deploys import DeployError, DeployRecord
from wrfdb_bot.wrf_data.store import DataSnapshot


@dataclass(frozen=True)
class FrontendStatus:
    name: str
    url: str
    record: DeployRecord | None
    """What it serves now (its live /deploy.json); None if that couldn't be read."""
    relation: str
    """Its Data commit relative to the bot's, or why it is unknown."""


@dataclass(frozen=True)
class Status:
    data_version: str
    bot_commit: str | None
    site_build_id: str | None
    """The Site build the embed descriptions came from."""
    frontends: tuple[FrontendStatus, ...]


def gather(snapshot: DataSnapshot, data_repo: DataRepo, frontends: dict[str, str], fetch_live=deploys.fetch_live) -> Status:
    """Read everything /about shows. Blocks (git and network)."""
    bot_commit = data_repo.read_commit()
    statuses = []
    for name, url in frontends.items():
        try:
            record = fetch_live(url)
        except DeployError as e:
            statuses.append(FrontendStatus(name, url, None, f'unreadable: {e}'))
            continue
        statuses.append(FrontendStatus(name, url, record, relation(data_repo, bot_commit, record.data_commit)))
    return Status(snapshot.version, bot_commit, snapshot.meta_descriptions.build_id, tuple(statuses))


def relation(data_repo: DataRepo, bot_commit: str | None, commit: str) -> str:
    """Where `commit` stands against the bot's Data commit, in words."""
    if bot_commit is None:
        return "the bot's Data commit is unknown"
    if commit == bot_commit:
        return 'same as the bot'
    if data_repo.is_ancestor(commit, bot_commit):
        return f'{data_repo.count_commits(commit, bot_commit)} commit(s) behind the bot'
    if data_repo.is_ancestor(bot_commit, commit):
        return f'{data_repo.count_commits(bot_commit, commit)} commit(s) ahead of the bot'
    return "not in the bot's Data clone"
