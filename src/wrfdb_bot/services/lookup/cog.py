"""Lookup service Cog: answers `[[name]]` in messages and the `/wrf` command."""

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from wrfdb_bot.wrf_data.store import DataSnapshot

from .embeds import reply_kwargs
from .index import LookupIndex
from .query_parser import extract_queries

if TYPE_CHECKING:
    from wrfdb_bot.bot import WrfBot

MAX_CHOICE_LENGTH = 100


class LookupCog(commands.Cog):
    def __init__(self, bot: 'WrfBot'):
        self.bot = bot
        self._index: LookupIndex | None = None
        self._index_snapshot: DataSnapshot | None = None

    @property
    def index(self) -> LookupIndex:
        """The index for the current data, rebuilt after the DataStore refreshes."""
        snapshot = self.bot.data_store.snapshot
        if self._index is None or snapshot is not self._index_snapshot:
            self._index = LookupIndex.from_snapshot(snapshot)
            self._index_snapshot = snapshot
        return self._index

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        queries = extract_queries(message.content)
        if not queries:
            return
        index = self.index
        results = [index.resolve(q) for q in queries]
        await message.reply(mention_author=False, **reply_kwargs(results, index.version))

    @app_commands.command(name='wrf', description='Look up a War Robots: Frontiers robot, pilot, module, ...')
    @app_commands.describe(query='Name to look up, optionally with a type prefix (talent:Vanguard)')
    async def wrf(self, interaction: discord.Interaction, query: str) -> None:
        index = self.index
        result = index.resolve(query)
        await interaction.response.send_message(
            ephemeral=result.entry is None, **reply_kwargs([result], index.version)
        )

    @wrf.autocomplete('query')
    async def wrf_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(
                name=f'{e.display_name} ({e.object_type.label})'[:MAX_CHOICE_LENGTH],
                value=e.hint[:MAX_CHOICE_LENGTH],
            )
            for e in self.index.autocomplete(current)
        ]


async def setup(bot: 'WrfBot') -> None:
    await bot.add_cog(LookupCog(bot))
