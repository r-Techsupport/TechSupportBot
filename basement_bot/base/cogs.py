"""Base cogs for making plugins.
"""


import asyncio

import munch
from discord.ext import commands


class BaseCog(commands.Cog):
    """The base plugin.

    parameters:
        bot (Bot): the bot object
        models (List[gino.Model]): the Postgres models for the plugin
        no_guild (bool): True if the plugin should run globally
    """

    COG_TYPE = "Base"
    ADMIN_ONLY = False
    KEEP_COG_ON_FAILURE = False
    KEEP_PLUGIN_ON_FAILURE = False

    def __init__(self, bot, models=None, plugin_name=None, no_guild=False):
        self.bot = bot
        self.no_guild = no_guild

        # this is sure to throw a bug at some point
        self.extension_name = plugin_name

        if models is None:
            models = []
        self.models = munch.Munch()
        for model in models:
            self.models[model.__name__] = model

        self.bot.loop.create_task(self._preconfig())

    async def _handle_preconfig(self, handler):
        """Wrapper for performing preconfig on a plugin.

        This makes the plugin unload when there is an error.

        parameters:
            handler (asyncio.coroutine): the preconfig handler
        """
        await self.bot.wait_until_ready()
        try:
            await handler()
        except Exception as e:
            await self.bot.logger.error(
                f"Cog preconfig error: {handler.__name__}!", exception=e
            )
            if not self.KEEP_COG_ON_FAILURE:
                self.bot.remove_cog(self)
            if not self.KEEP_PLUGIN_ON_FAILURE:
                self.bot.unload_plugin(self.extension_name)

    async def _preconfig(self):
        """Blocks the preconfig until the bot is ready."""
        await self._handle_preconfig(self.preconfig)

    async def preconfig(self):
        """Preconfigures the environment before starting the plugin."""


class MatchCog(BaseCog):
    """
    Plugin for matching a specific context criteria and responding.

    This makes the process of handling events simpler for development.
    """

    COG_TYPE = "Match"

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listens for a message and passes it to the response handler if valid.

        parameters:
            message (message): the message object
        """
        if message.author == self.bot.user:
            return

        ctx = await self.bot.get_context(message)

        config = await self.bot.get_context_config(ctx)
        if not config:
            return

        result = await self.match(config, ctx, message.content)
        if not result:
            return

        try:
            await self.response(config, ctx, message.content, result)
        except Exception as e:
            await self.bot.logger.debug("Checking config for log channel")
            config = await self.bot.get_context_config(ctx)
            channel = config.get("logging_channel")
            await self.bot.logger.error(
                f"Match cog error: {self.__class__.__name__}!",
                exception=e,
                channel=channel,
            )

    async def match(self, _config, _ctx, _content):
        """Runs a boolean check on message content.

        parameters:
            config (dict): the config associated with the context
            ctx (context): the context object
            content (str): the message content
        """
        return True

    async def response(self, _config, _ctx, _content, _result):
        """Performs a response if the match is valid.

        parameters:
            config (dict): the config associated with the context
            ctx (context): the context object
            content (str): the message content
        """


class LoopCog(BaseCog):
    """Plugin for various types of looping including cron-config.

    This currently doesn't utilize the tasks library.

    parameters:
        bot (Bot): the bot object
    """

    COG_TYPE = "Loop"
    DEFAULT_WAIT = 300
    TRACKER_WAIT = 300
    ON_START = False
    CHANNELS_KEY = "channels"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot.loop.create_task(self._loop_preconfig())
        self.channels = {}

    async def register_new_tasks(self, guild):
        """Creates the configured loop tasks for a given guild.

        parameters:
            guild (discord.Guild): the guild to add the tasks for
        """
        config = await self.bot.get_context_config(guild=guild)
        channels = (
            config.plugins.get(self.extension_name, {})
            .get(self.CHANNELS_KEY, {})
            .get("value")
        )
        if channels is not None:
            self.channels[guild.id] = [
                self.bot.get_channel(int(ch_id)) for ch_id in channels
            ]

        if self.channels.get(guild.id):
            for channel in self.channels.get(guild.id, []):
                await self.bot.logger.debug(
                    f"Creating loop task for channel with ID {channel.id}"
                )
                self.bot.loop.create_task(self._loop_execute(guild, channel))
        else:
            await self.bot.logger.debug(
                f"Creating loop task for guild with ID {guild.id}"
            )
            self.bot.loop.create_task(self._loop_execute(guild))

    async def _loop_preconfig(self):
        """Blocks the loop_preconfig until the bot is ready."""
        await self._handle_preconfig(self.loop_preconfig)

        if self.no_guild:
            await self.bot.logger.debug("Creating loop task for guild with no ID")
            self.bot.loop.create_task(self._loop_execute(None))
            return

        for guild in self.bot.guilds:
            await self.register_new_tasks(guild)

    async def _track_new_channels(self):
        """Periodifically kicks off new per-channel tasks based on updated channels config."""
        while True:
            await self.bot.logger.debug(
                f"Sleeping for {self.TRACKER_WAIT} seconds before checking channel config"
            )
            await asyncio.sleep(self.TRACKER_WAIT)

            await self.bot.logger.info(
                f"Checking registered channels for {self.extension_name} loop plugin"
            )
            for guild_id, registered_channels in self.channels.items():
                guild = self.bot.get_guild(guild_id)
                config = await self.bot.get_context_config(guild=guild)
                configured_channels = (
                    config.plugins.get(self.extension_name, {})
                    .get(self.CHANNELS_KEY, {})
                    .get("value")
                )
                if not isinstance(configured_channels, list):
                    await self.bot.logger.error(
                        f"Configured channels no longer readable for guild with ID {guild_id} - deleting registration"
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
                        await self.bot.logger.debug(
                            f"Could not find channel with ID {channel_id} - moving on"
                        )
                        continue

                    if not channel.id in [ch.id for ch in registered_channels]:
                        await self.bot.logger.debug(
                            f"Found new channel with ID {channel.id} in loop config - starting task"
                        )
                        self.bot.loop.create_task(self._loop_execute(guild, channel))

                    new_registered_channels.append(channel)

                registered_channels = new_registered_channels

    async def loop_preconfig(self):
        """Preconfigures the environment before starting the loop."""

    async def _loop_execute(self, guild, target_channel=None):
        """Loops through the execution method.

        parameters:
            guild (discord.Guild): the guild associated with the execution
        """
        config = await self.bot.get_context_config(guild=guild)

        if not self.ON_START:
            await self.wait(config, guild)

        while self.bot.plugins.get(self.extension_name):
            if guild and guild not in self.bot.guilds:
                break

            # refresh the config on every loop step
            config = await self.bot.get_context_config(guild=guild)

            if target_channel and not str(target_channel.id) in config.plugins.get(
                self.extension_name, {}
            ).get(self.CHANNELS_KEY, {}).get("value", []):
                # exit task if the channel is no longer configured
                break

            try:
                if target_channel:
                    await self.execute(config, guild, target_channel)
                else:
                    await self.execute(config, guild)
            except Exception as e:
                # always try to wait even when execute fails
                await self.bot.logger.debug("Checking config for log channel")
                channel = config.get("logging_channel")
                await self.bot.logger.error(
                    f"Loop cog execute error: {self.__class__.__name__}!",
                    exception=e,
                    channel=channel,
                )

            try:
                await self.wait(config, guild)
            except Exception as e:
                await self.bot.logger.error(
                    f"Loop wait cog error: {self.__class__.__name__}!", exception=e
                )
                # avoid spamming
                await self._default_wait()

    async def execute(self, _config, _guild, _target_channel=None):
        """Runs sequentially after each wait method.

        parameters:
            config (munch.Munch): the config object for the guild
            guild (discord.Guild): the guild associated with the execution
            target_channel (discord.Channel): the channel object to use
        """

    async def _default_wait(self):
        """The default method used for waiting."""
        await asyncio.sleep(self.DEFAULT_WAIT)

    async def wait(self, _config, _guild):
        """The default wait method.

        parameters:
            config (munch.Munch): the config object for the guild
            guild (discord.Guild): the guild associated with the execution
        """
        await self._default_wait()
