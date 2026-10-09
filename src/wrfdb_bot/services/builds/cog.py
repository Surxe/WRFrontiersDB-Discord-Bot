"""Builds service Cog: answers `/models?a=<code>` links in messages, and `/wrf-build`, with the
builds' parts."""

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .embeds import reply_kwargs
from .links import find_codes, models_url, parse_build_arg, read_link

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

    @app_commands.command(name='wrf-build', description='Show the parts of a War Robots: Frontiers build code')
    @app_commands.describe(build='A build code, two codes to compare (A B), or a wrf-db.info /models link')
    async def wrf_build(self, interaction: discord.Interaction, build: str) -> None:
        site_url = self.bot.data_store.site_url
        snapshot = self.bot.data_store.snapshot
        codes = parse_build_arg(build, site_url)
        if snapshot.build_codes is None:
            await interaction.response.send_message("The bot can't read build codes right now.", ephemeral=True)
            return
        if codes is None:
            await interaction.response.send_message(
                'Give one build code, two codes separated by a space (A B), or a /models link.', ephemeral=True
            )
            return
        link = read_link(snapshot, snapshot.build_codes, *codes)
        await interaction.response.send_message(
            ephemeral=not link.builds,
            **reply_kwargs([link], snapshot.version, models_url(site_url, *codes) if link.builds else None),
        )


async def setup(bot: 'WrfBot') -> None:
    await bot.add_cog(BuildsCog(bot))
