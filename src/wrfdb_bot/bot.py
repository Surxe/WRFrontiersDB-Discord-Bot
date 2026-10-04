"""The Discord client: owns the shared data, loads the enabled services."""

import asyncio

import discord
from discord.ext import commands, tasks
from loguru import logger

from .options import Options
from .wrf_data.data_repo import DataRepo
from .wrf_data.store import DataStore

# Service name (ENABLED_SERVICES) -> discord.py extension module with a `setup(bot)`.
SERVICE_EXTENSIONS: dict[str, str] = {
    'lookup': 'wrfdb_bot.services.lookup.cog',
}
# Services that read message text and so need the privileged Message Content intent.
MESSAGE_CONTENT_SERVICES = {'lookup'}


class WrfBot(commands.Bot):
    def __init__(self, options: Options):
        unknown = [s for s in options.enabled_services if s not in SERVICE_EXTENSIONS]
        if unknown:
            raise ValueError(f'Unknown ENABLED_SERVICES {unknown}; available: {sorted(SERVICE_EXTENSIONS)}')
        intents = discord.Intents.default()
        intents.message_content = bool(MESSAGE_CONTENT_SERVICES & set(options.enabled_services))
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)
        self.options = options
        self.data_store = DataStore(
            DataRepo(options.data.data_dir), options.data.site_url
        )
        self._refresh_data_loop = tasks.loop(minutes=options.data.data_refresh_minutes)(self._refresh_data)

    async def setup_hook(self) -> None:
        await asyncio.to_thread(self.data_store.load)
        for service in self.options.enabled_services:
            await self.load_extension(SERVICE_EXTENSIONS[service])
            logger.info(f'Loaded service {service}')
        await self._sync_commands()
        self._refresh_data_loop.start()

    async def on_ready(self) -> None:
        logger.info(f'Logged in as {self.user} in {len(self.guilds)} server(s)')

    async def _sync_commands(self) -> None:
        if not self.options.guild_ids:
            synced = await self.tree.sync()
            logger.info(f'Synced {len(synced)} global command(s); may take up to an hour to appear')
            return
        for guild_id in self.options.guild_ids:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f'Synced {len(synced)} command(s) to guild {guild_id}')

    async def _refresh_data(self) -> None:
        try:
            await asyncio.to_thread(self.data_store.refresh_if_changed)
        except Exception:
            logger.exception('Data refresh failed; keeping the current data')
