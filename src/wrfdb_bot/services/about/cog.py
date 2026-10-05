"""About service Cog: `/about` says which WRF data the bot and the frontends are on."""

import asyncio
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .status import Status, gather

if TYPE_CHECKING:
    from wrfdb_bot.bot import WrfBot

EMBED_COLOUR = discord.Colour(0x3B82F6)


class AboutCog(commands.Cog):
    def __init__(self, bot: 'WrfBot'):
        self.bot = bot

    @app_commands.command(name='about', description='Which WRF data the bot, the Site and the Visualizer are on')
    async def about(self, interaction: discord.Interaction) -> None:
        # Reading the frontends' /deploy.json can take longer than Discord's 3 s reply window.
        await interaction.response.defer(ephemeral=True)
        store = self.bot.data_store
        frontends = {'Site': store.site_url, 'Visualizer': self.bot.options.data.visualizer_url}
        status = await asyncio.to_thread(gather, store.snapshot, store.data_repo, frontends)
        await interaction.followup.send(embed=status_embed(status), ephemeral=True)


def status_embed(status: Status) -> discord.Embed:
    embed = discord.Embed(title='WRFrontiersDB data', colour=EMBED_COLOUR)
    embed.add_field(name='Bot', value=f'Data {status.data_version} - `{_short(status.bot_commit)}`', inline=False)
    for frontend in status.frontends:
        record = frontend.record
        if record is None:
            value = frontend.relation
        else:
            value = f'Data {record.data_version} - `{record.short_commit}` - {frontend.relation}'
            built = (record.built_at_utc or '?').replace('T', ' ').replace('Z', ' UTC')
            value += f'\nBuilt {built}' + (f' ([run]({record.run_url}))' if record.run_url else '')
        embed.add_field(name=frontend.name, value=value, inline=False)
    embed.set_footer(text=f'Embed descriptions from Site build {status.site_build_id or "none"}')
    return embed


def _short(commit: str | None) -> str:
    return commit[:7] if commit else 'unknown'


async def setup(bot: 'WrfBot') -> None:
    await bot.add_cog(AboutCog(bot))
