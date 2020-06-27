"""Base cogs for making plugins.
"""

import asyncio

from discord.ext import commands

from utils.logger import get_logger

log = get_logger("Cogs")


class BasicPlugin(commands.Cog):
    """The base plugin.

    parameters:
        bot (Bot): the bot object
    """

    PLUGIN_TYPE = "BASIC"

    def __init__(self, bot):
        self.bot = bot


class MatchPlugin(BasicPlugin):
    """Plugin for matching a specific criteria and responding.
    """

    PLUGIN_TYPE = "MATCH"

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listens for a message and passes it to the response handler if valid.

        parameters:
            message (message): the message object
        """
        if message.author == self.bot.user:
            return

        ctx = await self.bot.get_context(message)

        try:
            if self.match(message.content):
                await self.response(ctx, message.content)
        except Exception as e:
            log.exception(e)

    def match(self, content):
        """Runs a boolean check on message content.

        parameters:
            content (str): the message content
        """
        raise RuntimeError("Match function must be defined in sub-class")

    async def response(self, ctx, content):
        """Performs a response if the match is valid.

        parameters:
            ctx (context): the context object
            content (str): the message content
        """
        raise RuntimeError("Response function must be defined in sub-class")


class LoopPlugin(BasicPlugin):
    """Plugin for looping a task.

    parameters:
        bot (Bot): the bot object
    """

    PLUGIN_TYPE = "LOOP"
    DEFAULT_WAIT = 30

    def __init__(self, bot):
        super().__init__(bot)
        self.state = False
        self.bot.loop.create_task(self._loop_execute())

    async def _loop_execute(self):
        """Loops through the execution method.
        """
        await self.preconfig()
        self.state = True
        while self.state:
            await self.bot.loop.create_task(
                self.execute()
            )  # pylint: disable=not-callable
            await self.wait()

    def cog_unload(self):
        """Allows the state to exit after unloading.
        """
        self.state = False

    async def wait(self):
        """The default wait method.
        """
        await asyncio.sleep(self.DEFAULT_WAIT)

    async def preconfig(self):
        """Preconfigures the environment before starting the loop.
        """
        raise RuntimeError("Preconfig function must be defined in sub-class")

    async def execute(self):
        """Runs sequentially after each wait method.
        """
        raise RuntimeError("Execute function must be defined in sub-class")
