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
                self.bot.plugin_api.unload_plugin(self.extension_name)

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

        await self.response(config, ctx, message.content)

    async def match(self, _config, _ctx, _content):
        """Runs a boolean check on message content.

        parameters:
            config (dict): the config associated with the context
            ctx (context): the context object
            content (str): the message content
        """
        return True

    async def response(self, _config, _ctx, _content):
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

    DEFAULT_WAIT = 300
    ON_START = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot.loop.create_task(self._loop_preconfig())

    async def _loop_preconfig(self):
        """Blocks the loop_preconfig until the bot is ready."""
        await self._handle_preconfig(self.loop_preconfig)

        if self.no_guild:
            self.bot.loop.create_task(self._loop_execute(None))
            return

        for guild in self.bot.guilds:
            self.bot.loop.create_task(self._loop_execute(guild))

    async def loop_preconfig(self):
        """Preconfigures the environment before starting the loop."""

    async def _loop_execute(self, guild):
        """Loops through the execution method.

        parameters:
            guild (discord.Guild): the guild associated with the execution
        """
        config = await self.bot.get_context_config(guild=guild)

        if not self.ON_START:
            await self.wait(config, guild)

        while self.bot.plugin_api.plugins.get(self.extension_name):
            # refresh the config on every loop step
            config = await self.bot.get_context_config(guild=guild)

            try:
                await self.execute(config, guild)
            except Exception as e:
                # always try to wait even when execute fails
                await self.bot.logger.debug("Checking config for log channel")
                channel = config.get("log_channel")

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

    async def execute(self, _config, _guild):
        """Runs sequentially after each wait method.

        parameters:
            config (munch.Munch): the config object for the guild
            guild (discord.Guild): the guild associated with the execution
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
