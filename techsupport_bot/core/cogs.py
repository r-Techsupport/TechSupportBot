"""Base cogs for making extentions."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, List

import discord
import gino
import munch
from botlogging import LogContext, LogLevel
from discord.ext import commands

if TYPE_CHECKING:
    import bot


class BaseCog(commands.Cog):
    """The base cog to use when making extensions.

    parameters:
        bot (Bot): the bot object
        models (List[gino.Model]): the Postgres models for the extension
        no_guild (bool): True if the extension should run globally
    """

    COG_TYPE = "Base"
    KEEP_COG_ON_FAILURE = False

    def __init__(
        self,
        bot: bot.TechSupportBot,
        models: List[gino.Model] = None,
        no_guild: bool = False,
        extension_name: str = None,
    ) -> None:
        self.bot = bot
        self.no_guild = no_guild
        self.extension_name = extension_name

        if models is None:
            models = []
        self.models = munch.Munch()
        for model in models:
            self.models[model.__name__] = model

        asyncio.create_task(self._preconfig())

    async def _handle_preconfig(self, handler) -> None:
        """Wrapper for performing preconfig on an extension.

        This makes the extension unload when there is an error.

        parameters:
            handler (asyncio.coroutine): the preconfig handler
        """
        await self.bot.wait_until_ready()

        try:
            await handler()
        except Exception as exception:
            await self.bot.logger.send_log(
                message=f"Cog preconfig error: {handler.__name__}!",
                level=LogLevel.ERROR,
                exception=exception,
            )
            if not self.KEEP_COG_ON_FAILURE:
                await self.bot.remove_cog(self)

    async def _preconfig(self) -> None:
        """Blocks the preconfig until the bot is ready."""
        await self._handle_preconfig(self.preconfig)

    async def preconfig(self) -> None:
        """Preconfigures the environment before starting the cog."""

    def extension_enabled(self, config: munch.Munch) -> bool:
        """Checks if an extension is currently enabled for a given config.

        parameters:
            config (dict): the context/guild config
        """
        if config is None:
            config = {}
        if self.no_guild or self.extension_name in config.get("enabled_extensions", []):
            return True
        return False


class MatchCog(BaseCog):
    """
    Cog for matching a specific context criteria and responding.

    This makes the process of handling events simpler for development.
    """

    COG_TYPE = "Match"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listens for a message and passes it to the response handler if valid.

        parameters:
            message (message): the message object
        """
        if message.author == self.bot.user:
            return

        ctx = await self.bot.get_context(message)

        config = self.bot.guild_configs[str(ctx.guild.id)]
        if not config:
            return

        if not self.extension_enabled(config):
            return

        result = await self.match(config, ctx, message.content)
        if not result:
            return

        try:
            await self.response(config, ctx, message.content, result)
        except Exception as exception:
            await self.bot.logger.send_log(
                message="Checking config for log channel",
                level=LogLevel.DEBUG,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
            )
            config = self.bot.guild_configs[str(ctx.guild.id)]
            channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message=f"Match cog error: {self.__class__.__name__} {exception}!",
                level=LogLevel.ERROR,
                channel=channel,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
                exception=exception,
            )

    async def match(
        self, _config: munch.Munch, _ctx: commands.Context, _content: str
    ) -> bool:
        """Runs a boolean check on message content.

        parameters:
            _config (dict): the config associated with the context
            _ctx (context): the context object
            _content (str): the message content
        """
        return True

    async def response(
        self, _config: munch.Munch, _ctx: commands.Context, _content: str, _result: bool
    ) -> None:
        """Performs a response if the match is valid.

        parameters:
            _config (dict): the config associated with the context
            _ctx (context): the context object
            _content (str): the message content
        """


class LoopCog(BaseCog):
    """Cog for various types of looping including cron-config.

    This currently doesn't utilize the tasks library.

    parameters:
        bot (Bot): the bot object
    """

    COG_TYPE: str = "Loop"
    DEFAULT_WAIT: int = 300
    TRACKER_WAIT: int = 300
    ON_START: bool = False
    CHANNELS_KEY: str = "channels"

    def __init__(self, *args: tuple, **kwargs: dict[str, Any]):
        super().__init__(*args, **kwargs)
        asyncio.create_task(self._loop_preconfig())
        self.channels = {}

    async def register_new_tasks(self, guild: discord.Guild) -> None:
        """Creates the configured loop tasks for a given guild.

        parameters:
            guild (discord.Guild): the guild to add the tasks for
        """
        config = self.bot.guild_configs[str(guild.id)]
        channels = (
            config.extensions.get(self.extension_name, {})
            .get(self.CHANNELS_KEY, {})
            .get("value")
        )
        if channels is not None:
            channels = sorted(set(channels))
            self.channels[guild.id] = [
                self.bot.get_channel(int(ch_id)) for ch_id in channels
            ]

        if self.channels.get(guild.id):
            for channel in self.channels.get(guild.id, []):
                await self.bot.logger.send_log(
                    message=f"Creating loop task for channel with ID {channel.id}",
                    level=LogLevel.DEBUG,
                    context=LogContext(guild=channel.guild, channel=channel),
                )
                asyncio.create_task(self._loop_execute(guild, channel))
        else:
            await self.bot.logger.send_log(
                message=f"Creating loop task for guild with ID {guild.id}",
                level=LogLevel.DEBUG,
                context=LogContext(guild=guild),
            )
            asyncio.create_task(self._loop_execute(guild))

    async def _loop_preconfig(self) -> None:
        """Blocks the loop_preconfig until the bot is ready."""
        await self._handle_preconfig(self.loop_preconfig)

        if self.no_guild:
            await self.bot.logger.send_log(
                message="Creating global loop task",
                level=LogLevel.DEBUG,
            )
            asyncio.create_task(self._loop_execute(None))
            return

        for guild in self.bot.guilds:
            await self.register_new_tasks(guild)

        asyncio.create_task(self._track_new_channels())

    async def _track_new_channels(self) -> None:
        """Periodifically kicks off new per-channel tasks based on updated channels config."""
        while True:
            await self.bot.logger.send_log(
                message=(
                    f"Sleeping for {self.TRACKER_WAIT} seconds before checking channel"
                    " config"
                ),
                level=LogLevel.DEBUG,
            )
            await asyncio.sleep(self.TRACKER_WAIT)

            await self.bot.logger.send_log(
                message=(
                    f"Checking registered channels for {self.extension_name} loop cog"
                ),
                level=LogLevel.DEBUG,
            )
            for guild_id, registered_channels in self.channels.items():
                guild = self.bot.get_guild(guild_id)
                config = self.bot.guild_configs[str(guild.id)]
                configured_channels = (
                    config.extensions.get(self.extension_name, {})
                    .get(self.CHANNELS_KEY, {})
                    .get("value")
                )
                if not isinstance(configured_channels, list):
                    await self.bot.logger.send_log(
                        message=(
                            "Configured channels no longer readable for guild with ID"
                            f" {guild_id} - deleting registration"
                        ),
                        level=LogLevel.ERROR,
                        context=LogContext(guild=self.get_guild(guild_id)),
                    )
                    del registered_channels
                    continue

                new_registered_channels = []
                for channel_id in configured_channels:
                    try:
                        channel_id = int(channel_id)
                    except TypeError:
                        channel_id = 0

                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        await self.bot.logger.send_log(
                            message=(
                                f"Could not find channel with ID {channel_id} -"
                                " moving on"
                            ),
                            level=LogLevel.DEBUG,
                        )
                        continue

                    if channel.id not in [ch.id for ch in registered_channels]:
                        await self.bot.logger.send_log(
                            message=(
                                f"Found new channel with ID {channel.id} in loop config"
                                " - starting task"
                            ),
                            level=LogLevel.DEBUG,
                            context=LogContext(guild=channel.guild, channel=channel),
                        )
                        asyncio.create_task(self._loop_execute(guild, channel))

                    new_registered_channels.append(channel)

                registered_channels = new_registered_channels

    async def loop_preconfig(self) -> None:
        """Preconfigures the environment before starting the loop."""

    async def _loop_execute(self, guild: discord.Guild, target_channel=None) -> None:
        """Loops through the execution method.

        parameters:
            guild (discord.Guild): the guild associated with the execution
        """
        config = self.bot.guild_configs[str(guild.id)]

        if not self.ON_START:
            await self.wait(config, guild)

        for folder_dir in [self.bot.EXTENSIONS_DIR_NAME, self.bot.FUNCTIONS_DIR_NAME]:
            while self.bot.extensions.get(f"{folder_dir}.{self.extension_name}"):
                if guild and guild not in self.bot.guilds:
                    break

                # refresh the config on every loop step
                config = self.bot.guild_configs[str(guild.id)]

                if target_channel and not str(
                    target_channel.id
                ) in config.extensions.get(self.extension_name, {}).get(
                    self.CHANNELS_KEY, {}
                ).get(
                    "value", []
                ):
                    # exit task if the channel is no longer configured
                    break

                if guild is None or self.extension_name in getattr(
                    config, "enabled_extensions", []
                ):
                    try:
                        if target_channel:
                            await self.execute(config, guild, target_channel)
                        else:
                            await self.execute(config, guild)
                    except Exception as exception:
                        # always try to wait even when execute fails
                        await self.bot.logger.send_log(
                            message=f"Loop cog execute error: {self.__class__.__name__}!",
                            level=LogLevel.ERROR,
                            channel=getattr(config, "logging_channel", None),
                            context=LogContext(guild=guild),
                            exception=exception,
                        )

                try:
                    await self.wait(config, guild)
                except Exception as exception:
                    await self.bot.logger.send_log(
                        message=f"Loop wait cog error: {self.__class__.__name__}!",
                        level=LogLevel.ERROR,
                        context=LogContext(guild=guild),
                        exception=exception,
                    )
                    # avoid spamming
                    await self._default_wait()

    async def execute(
        self,
        _config: munch.Munch,
        _guild: discord.Guild,
        _target_channel: discord.abc.Messageable = None,
    ) -> None:
        """Runs sequentially after each wait method.

        parameters:
            _config (munch.Munch): the config object for the guild
            _guild (discord.Guild): the guild associated with the execution
            _target_channel (discord.Channel): the channel object to use
        """

    async def _default_wait(self) -> None:
        """The default method used for waiting."""
        await asyncio.sleep(self.DEFAULT_WAIT)

    async def wait(self, _config: munch.Munch, _guild: discord.Guild) -> None:
        """The default wait method.

        parameters:
            _config (munch.Munch): the config object for the guild
            _guild (discord.Guild): the guild associated with the execution
        """
        await self._default_wait()
