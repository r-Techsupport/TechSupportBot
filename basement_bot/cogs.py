"""Base cogs for making plugins.
"""

import asyncio

import aiocron
import http3
from discord.ext import commands
from sqlalchemy.ext.declarative import declarative_base

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
        self.bot.loop.create_task(self.preconfig())

    async def preconfig(self):
        """Preconfigures the environment before starting the plugin.
        """


class HttpPlugin(BasicPlugin):
    """Plugin for interfacing via HTTP.
    """

    PLUGIN_TYPE = "HTTP"

    @staticmethod
    def _get_client():
        return http3.AsyncClient()

    async def http_call(self, method, *args):
        """Makes an HTTP request.

        args:
            method (string): the HTTP method to use
            *args (...): the args with which to call the HTTP Python method
        """
        client = self._get_client()
        method_fn = getattr(client, method.lower(), None)
        if not method_fn:
            raise AttributeError(f"Unable to use HTTP method: {method}")
        response = await method_fn(*args)
        return response


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
            if self.match(ctx, message.content):
                await self.response(ctx, message.content)
        except Exception as e:
            log.exception(e)

    def match(self, ctx, content):
        """Runs a boolean check on message content.

        parameters:
            ctx (context): the context object
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


class DatabasePlugin(BasicPlugin):
    """Plugin for accessing the database.
    """

    PLUGIN_TYPE = "DATABASE"
    BaseTable = declarative_base()

    def __init__(self, bot, model=None):
        super().__init__(bot)
        self.model = model
        if self.model:
            self.bot.database_api.create_table(self.model)
        self.bot.loop.create_task(self.db_preconfig())
        self.db_session = self.bot.database_api.get_session

    async def db_preconfig(self):
        """Preconfigures the environment before starting the plugin.
        """


class LoopPlugin(BasicPlugin):
    """Plugin for looping a task.

    parameters:
        bot (Bot): the bot object
    """

    PLUGIN_TYPE = "LOOP"
    DEFAULT_WAIT = 30
    CRON_CONFIG = None

    def __init__(self, bot):
        super().__init__(bot)
        self.state = True
        self.bot.loop.create_task(self._loop_execute())

    async def _loop_execute(self):
        """Loops through the execution method.
        """
        await self.bot.wait_until_ready()
        await self.loop_preconfig()
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
        if self.CRON_CONFIG:
            await aiocron.crontab(self.CRON_CONFIG).next()
        else:
            await asyncio.sleep(self.DEFAULT_WAIT)

    async def loop_preconfig(self):
        """Preconfigures the environment before starting the loop.
        """

    async def execute(self):
        """Runs sequentially after each wait method.
        """
        raise RuntimeError("Execute function must be defined in sub-class")
