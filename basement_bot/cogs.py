"""Base cogs for making plugins.
"""

import asyncio
import logging

import aiocron
import http3
import pika
from discord.ext import commands
from sqlalchemy.ext.declarative import declarative_base

from utils.logger import get_logger

logging.getLogger("pika").setLevel(logging.WARNING)
log = get_logger("Cogs")


class BasicPlugin(commands.Cog):
    """The base plugin.

    parameters:
        bot (Bot): the bot object
    """

    PLUGIN_TYPE = "BASIC"
    PLUGIN_NAME = None
    HAS_CONFIG = True

    def __init__(self, bot):
        self.bot = bot

        if self.PLUGIN_NAME and "." in self.PLUGIN_NAME:
            self.PLUGIN_NAME = self.PLUGIN_NAME.split(".")[1]
        self.config = self.bot.config.plugins.get(f"{self.PLUGIN_NAME}")
        if not self.config and self.HAS_CONFIG:
            if not self.PLUGIN_NAME:
                raise ValueError(
                    f"PLUGIN_NAME not provided for plugin {self.__class__.__name__}"
                )
            else:
                raise ValueError(
                    f"No valid configuration found for plugin {self.PLUGIN_NAME}"
                )

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
        """Returns an Async HTTP client.
        """
        return http3.AsyncClient()

    async def http_call(self, method, *args, **kwargs):
        """Makes an HTTP request.

        args:
            method (string): the HTTP method to use
            *args (...list): the args with which to call the HTTP Python method
            **kwargs (...dict): the keyword args with which to call the HTTP Python method
        """
        client = self._get_client()
        method_fn = getattr(client, method.lower(), None)
        if not method_fn:
            raise AttributeError(f"Unable to use HTTP method: {method}")
        log.debug(f"Making {method} HTTP call on URL: {args}")
        response = await method_fn(*args, **kwargs)
        log.debug(f"Received HTTP response: {response.json()}")
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
    WAIT_KEY = None

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
        if self.config.get("cron_config"):
            await aiocron.crontab(self.config.cron_config).next()
        else:
            await asyncio.sleep(self.config.get(self.WAIT_KEY) or self.DEFAULT_WAIT)

    async def loop_preconfig(self):
        """Preconfigures the environment before starting the loop.
        """

    async def execute(self):
        """Runs sequentially after each wait method.
        """
        raise RuntimeError("Execute function must be defined in sub-class")


class MqPlugin(BasicPlugin):
    """Plugin for sending and receiving queue events.

    parameters:
        bot (Bot): the bot object
    """

    PLUGIN_TYPE = "MQ"

    connection = None
    mq_error_state = False

    # pylint: disable=attribute-defined-outside-init
    def connect(self):
        """Sets the connection attribute to an active connection.
        """

        self.parameters = pika.ConnectionParameters(
            self.config.mq_host,
            self.config.mq_port,
            self.config.mq_vhost,
            pika.PlainCredentials(self.config.mq_user, self.config.mq_pass),
        )
        try:
            self.connection = pika.BlockingConnection(self.parameters)
            return True
        except Exception as e:
            e = str(e) or "No route to host"  # dumb correction to a blank error
            log.warning(f"Unable to connect to MQ: {e}")
        return False

    def publish(self, bodies):
        """Sends a list of events to the event queue.

        parameters:
            bodies (list): the list of events
        """
        while True:
            try:
                mq_channel = self.connection.channel()
                mq_channel.queue_declare(queue=self.config.mq_send_queue, durable=True)
                for body in bodies:
                    mq_channel.basic_publish(
                        exchange="", routing_key=self.config.mq_send_queue, body=body
                    )
                self.mq_error_state = False
                break
            except Exception as e:
                if self.connection is not None:
                    log.debug(self.connection)
                    log.debug(f"Unable to publish: {e}")
                if not self.connect():
                    self.mq_error_state = True
                    break

    def consume(self):
        """Retrieves a list of events from the event queue.
        """
        bodies = []

        while True:
            try:
                mq_channel = self.connection.channel()
                mq_channel.queue_declare(queue=self.config.mq_recv_queue, durable=True)
                checks = 0
                while checks < self.config.response_limit:
                    body = self._get_ack(mq_channel)
                    checks += 1
                    if not body:
                        break
                    bodies.append(body)
                self.mq_error_state = False
                break
            except Exception as e:
                if self.connection is not None:
                    log.debug(f"Unable to consume: {e}")
                if not self.connect():
                    self.mq_error_state = True
                    break

        return bodies

    def _get_ack(self, channel):
        """Gets a body and acknowledges its consumption.

        parameters:
            channel (PikaChannel): the channel on which to consume
        """
        method, _, body = channel.basic_get(queue=self.config.mq_recv_queue)
        if method:
            channel.basic_ack(method.delivery_tag)
        return body
