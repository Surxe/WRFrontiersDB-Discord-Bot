"""Builds service Cog: answers `/models?a=<code>` links in messages with the builds' parts."""

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from .embeds import reply_kwargs
from .links import find_codes, read_link

if TYPE_CHECKING:
    from wrfdb_bot.bot import WrfBot


class BuildsCog(commands.Cog):
    def __init__(self, bot: 'WrfBot'):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        found = find_codes(message.content, self.bot.data_store.site_url)
        if not found:
            return
        snapshot = self.bot.data_store.snapshot
        if snapshot.build_codes is None:
            return
        links = [read_link(snapshot, snapshot.build_codes, a, b) for a, b in found]
        await message.reply(mention_author=False, **reply_kwargs(links, snapshot.version))


async def setup(bot: 'WrfBot') -> None:
    await bot.add_cog(BuildsCog(bot))
