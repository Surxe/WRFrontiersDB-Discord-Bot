"""The Discord client: owns the shared data, loads the enabled services."""

import asyncio

import discord
from discord.ext import commands, tasks
from loguru import logger

from .heartbeat import touch_heartbeat
from .options import Options
from .wrf_data.data_repo import DataRepo
from .wrf_data.store import DataStore

# Service name (ENABLED_SERVICES) -> discord.py extension module with a `setup(bot)`.
SERVICE_EXTENSIONS: dict[str, str] = {
    'lookup': 'wrfdb_bot.services.lookup.cog',
    'about': 'wrfdb_bot.services.about.cog',
    'builds': 'wrfdb_bot.services.builds.cog',
}
# Services that read message text and so need the privileged Message Content intent.
MESSAGE_CONTENT_SERVICES = {'lookup', 'builds'}


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
            DataRepo(options.data.data_dir),
            options.data.site_url,
            options.data.site_deploy_state,
            options.data.data_raw_url,
        )
        self._refresh_data_loop = tasks.loop(minutes=options.data.data_refresh_minutes)(self._refresh_data)
        # Gateway state for the heartbeat: set on connect/resume, cleared on disconnect.
        self._gateway_connected = False
        self._heartbeat_loop = tasks.loop(minutes=1)(self._heartbeat)

    async def setup_hook(self) -> None:
        await asyncio.to_thread(self.data_store.load)
        for service in self.options.enabled_services:
            await self.load_extension(SERVICE_EXTENSIONS[service])
            logger.info(f'Loaded service {service}')
        await self._sync_commands()
        self._refresh_data_loop.start()
        if self.options.heartbeat_file:
            self._heartbeat_loop.start()

    async def on_ready(self) -> None:
        logger.info(f'Logged in as {self.user} in {len(self.guilds)} server(s)')

    async def on_connect(self) -> None:
        self._gateway_connected = True

    async def on_resumed(self) -> None:
        self._gateway_connected = True

    async def on_disconnect(self) -> None:
        self._gateway_connected = False

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

    async def _heartbeat(self) -> None:
        # Touched only while connected, so the file's age is how long the bot has been
        # unreachable (read by home-server's availability log).
        if self._gateway_connected:
            touch_heartbeat(self.options.heartbeat_file)

    async def _refresh_data(self) -> None:
        try:
            await asyncio.to_thread(self.data_store.refresh_if_changed)
        except Exception:
            logger.exception('Data refresh failed; keeping the current data')
