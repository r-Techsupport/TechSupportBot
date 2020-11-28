"""Base cogs for making plugins.
"""

import asyncio
import logging
from random import randint

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
            raise ValueError(
                f"No valid configuration found for plugin {self.PLUGIN_NAME}"
            )

        self.bot.loop.create_task(self.preconfig())

    async def preconfig(self):
        """Preconfigures the environment before starting the plugin."""


class HttpPlugin(BasicPlugin):
    """Plugin for interfacing via HTTP."""

    PLUGIN_TYPE = "HTTP"

    @staticmethod
    def _get_client():
        """Returns an Async HTTP client."""
        return http3.AsyncClient()

    async def http_call(self, method, *args, **kwargs):
        """Makes an HTTP request.

        parameters:
            method (string): the HTTP method to use
            *args (...list): the args with which to call the HTTP Python method
            **kwargs (...dict): the keyword args with which to call the HTTP Python method
        """
        client = self._get_client()
        method_fn = getattr(client, method.lower(), None)
        if not method_fn:
            raise AttributeError(f"Unable to use HTTP method: {method}")

        log.debug(f"Making {method} HTTP call on URL: {args}")
        try:
            response = await method_fn(*args, **kwargs)
        except Exception as e:
            log.error(f"Unable to process HTTP call: {e}")
            response = None

        if response:
            log.debug(f"Received HTTP response: {response.json()}")
        return response


class MatchPlugin(BasicPlugin):
    """Plugin for matching a specific criteria and responding."""

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
    """Plugin for accessing the database."""

    PLUGIN_TYPE = "DATABASE"
    BaseTable = declarative_base()
    MODEL = None

    def __init__(self, bot):
        super().__init__(bot)
        if self.MODEL:
            self.bot.database_api.create_table(self.MODEL)
        self.bot.loop.create_task(self.db_preconfig())
        self.db_session = self.bot.database_api.get_session

    async def db_preconfig(self):
        """Preconfigures the environment before starting the plugin."""


class LoopPlugin(BasicPlugin):
    """Plugin for looping a task.

    parameters:
        bot (Bot): the bot object
    """

    PLUGIN_TYPE = "LOOP"
    DEFAULT_WAIT = 30
    WAIT_KEY = None
    UNITS = "seconds"

    def __init__(self, bot):
        super().__init__(bot)
        self.state = True
        self.bot.loop.create_task(self._loop_execute())
        self.execution_locked = False

        if self.UNITS == "seconds":
            conversion_factor = 1
        elif self.UNITS == "minutes":
            conversion_factor = 60
        elif self.UNITS == "hours":
            conversion_factor = 3600

        self.conversion_factor = conversion_factor

    async def _loop_execute(self):
        """Loops through the execution method."""
        if not self.config.get("on_start"):
            await self.wait()

        await self.bot.wait_until_ready()
        await self.loop_preconfig()
        while self.state:
            if not self.execution_locked:
                await self.bot.loop.create_task(
                    self._execute()
                )  # pylint: disable=not-callable
                await self.wait()
            else:
                await asyncio.sleep(1)

    async def _execute(self):
        self.execution_locked = True
        await self.execute()
        self.execution_locked = False

    def cog_unload(self):
        """Allows the state to exit after unloading."""
        self.state = False

    # pylint: disable=method-hidden
    async def wait(self):
        """The default wait method."""
        if self.config.get("cron_config"):
            await aiocron.crontab(self.config.cron_config).next()
        else:
            if self.config.get(self.WAIT_KEY):
                sleep_time = self.config.get(self.WAIT_KEY) * self.conversion_factor
            else:
                sleep_time = self.DEFAULT_WAIT

            await asyncio.sleep(sleep_time)

    def setup_random_waiting(self, min_key, max_key):
        """Validates min and max wait times from config and sets the wait method to be random.

        parameters:
            min_key (str): the key to lookup the min wait config value
            max_key (str): the key to lookup the max wait config value
            units (str): the units that the wait times are in
        """
        min_wait = self.config.get(min_key)
        max_wait = self.config.get(max_key)
        if not min_wait or not max_wait:
            raise RuntimeError(
                f"Min and/or max wait times not found from keys {min_key}, {max_key}"
            )
        if min_wait < 0 or max_wait < 0:
            raise RuntimeError("Min and max times must both be greater than 0")
        if max_wait - min_wait <= 0:
            raise RuntimeError("Max time must be greater than min time")

        # pylint: disable=method-hidden
        async def random_wait():
            await asyncio.sleep(
                randint(
                    min_wait * self.conversion_factor, max_wait * self.conversion_factor
                )
            )

        self.wait = random_wait

    async def loop_preconfig(self):
        """Preconfigures the environment before starting the loop."""

    async def execute(self):
        """Runs sequentially after each wait method."""
        raise RuntimeError("Execute function must be defined in sub-class")


class MqPlugin(BasicPlugin):
    """Plugin for sending and receiving queue events.

    parameters:
        bot (Bot): the bot object
    """

    PLUGIN_TYPE = "MQ"

    connection = None

    # pylint: disable=attribute-defined-outside-init
    def connect(self):
        """Sets the connection attribute to an active connection."""

        self.parameters = pika.ConnectionParameters(
            self.config.mq_host,
            self.config.mq_port,
            self.config.mq_vhost,
            pika.PlainCredentials(self.config.mq_user, self.config.mq_pass),
        )
        try:
            self.connection = pika.BlockingConnection(self.parameters)
        except Exception as e:
            e = str(e) or "No route to host"  # dumb correction to a blank error
            log.warning(f"Unable to connect to MQ: {e}")

    def _close(self):
        """Attempts to close the connection."""
        try:
            self.connection.close()
        except Exception:
            pass

    def publish(self, bodies):
        """Sends a list of events to the event queue.

        parameters:
            bodies (list): the list of events
        """
        try:
            self.connect()
            mq_channel = self.connection.channel()
            mq_channel.queue_declare(queue=self.config.mq_send_queue, durable=True)
            for body in bodies:
                mq_channel.basic_publish(
                    exchange="", routing_key=self.config.mq_send_queue, body=body
                )
            return True
        except Exception as e:
            log.debug(f"Unable to publish: {e}")
            return False

        self._close()

    def consume(self):
        """Retrieves a list of events from the event queue."""
        bodies = []

        try:
            self.connect()
            mq_channel = self.connection.channel()
            mq_channel.queue_declare(queue=self.config.mq_recv_queue, durable=True)
            checks = 0
            while checks < self.config.response_limit:
                body = self._get_ack(mq_channel)
                checks += 1
                if not body:
                    break
                bodies.append(body)
            return bodies, True
        except Exception as e:
            log.debug(f"Unable to consume: {e}")
            return [], False

        self._close()

    def _get_ack(self, channel):
        """Gets a body and acknowledges its consumption.

        parameters:
            channel (PikaChannel): the channel on which to consume
        """
        method, _, body = channel.basic_get(queue=self.config.mq_recv_queue)
        if method:
            channel.basic_ack(method.delivery_tag)
        return body
