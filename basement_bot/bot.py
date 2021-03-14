"""The main bot functions.
"""

import asyncio
import collections
import datetime
import sys

import admin
import aio_pika
import aiohttp
import discord
import embed
import gino
import logger
import munch
import plugin
import yaml
from discord.ext import commands
from motor import motor_asyncio


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class BasementBot(commands.Bot):
    """The main bot object.

    parameters:
        run_on_init (bool): True if the bot should run on instantiation
    """

    CONFIG_PATH = "./config.yaml"
    GUILD_CONFIG_COLLECTION = "guild_config"

    PluginConfig = plugin.PluginConfig

    def __init__(self, run_on_init=True, intents=None):
        self.owner = None
        self.config = None
        self.mongo = None
        self.db = None
        self.rabbit = None
        self._startup_time = None
        self.guild_config_collection = None
        self.config_cache = collections.defaultdict(dict)

        self.logger = self.get_logger(self.__class__.__name__)

        self.load_bot_config(validate=True)

        self.plugin_api = plugin.PluginAPI(bot=self)
        self.embed_api = embed.EmbedAPI(bot=self)

        super().__init__(command_prefix=self.get_prefix, intents=intents)

        if not run_on_init:
            return

        self.run(self.config.main.auth_token)

    def load_bot_config(self, validate):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH) as iostream:
            config = yaml.safe_load(iostream)
        self.config = munch.munchify(config)

        self.config.main.disabled_plugins = self.config.main.disabled_plugins or []

        if not validate:
            return

        for subsection in ["required"]:
            self.validate_bot_config_subsection("main", subsection)

    def validate_bot_config_subsection(self, section, subsection):
        """Loops through a config subsection to check for missing values.

        parameters:
            section (str): the section name containing the subsection
            subsection (str): the subsection name
        """
        for key, value in self.config.get(section, {}).get(subsection, {}).items():
            error_key = None
            if value is None:
                error_key = key
            elif isinstance(value, dict):
                for k, v in value.items():
                    if v is None:
                        error_key = k
            if error_key:
                raise ValueError(
                    f"Config key {error_key} from {section}.{subsection} not supplied"
                )

    async def get_prefix(self, message):
        """Gets the appropriate prefix for a command.

        parameters:
            message (discord.Message): the message to check against
        """
        guild_config = await self.get_context_config(ctx=None, guild=message.guild)
        return getattr(guild_config, "command_prefix", self.config.main.default_prefix)

    def run(self, *args, **kwargs):
        """Starts the event loop and blocks until interrupted."""
        try:
            self.loop.run_until_complete(self.start(*args, **kwargs))
        except (SystemExit, KeyboardInterrupt):
            self.loop.run_until_complete(self.cleanup())
        finally:
            self.loop.close()

    async def start(self, *args, **kwargs):
        """Sets up config and connections then starts the actual bot."""
        # this is required for the bot
        await self.logger.debug("Connecting to MongoDB...")
        self.mongo = self.get_mongo_ref()

        if not self.GUILD_CONFIG_COLLECTION in await self.mongo.list_collection_names():
            await self.logger.debug("Creating new MongoDB guild config collection...")
            await self.mongo.create_collection(self.GUILD_CONFIG_COLLECTION)

        self.guild_config_collection = self.mongo[self.GUILD_CONFIG_COLLECTION]
        self.loop.create_task(self.reset_config_cache())

        await self.logger.debug("Connecting to Postgres...")
        try:
            self.db = await self.get_postgres_ref()
        except Exception as exception:
            await self.logger.warning(f"Could not connect to Postgres: {exception}")

        await self.logger.debug("Connecting to RabbitMQ...")
        try:
            self.rabbit = await self.get_rabbit_connection()
        except Exception as exception:
            await self.logger.warning(f"Could not connect to RabbitMQ: {exception}")

        await self.logger.debug("Loading plugins...")
        self.plugin_api.load_plugins()

        if self.db:
            await self.logger.debug("Syncing Postgres tables...")
            await self.db.gino.create_all()

        await self.logger.debug("Loading Admin extension...")
        try:
            self.add_cog(admin.AdminControl(self))
        except (TypeError, commands.CommandError) as exception:
            await self.logger.warning(
                f"Could not load Admin extension! Error: {exception}"
            )

        await self.logger.debug("Logging into Discord...")
        await super().start(*args, **kwargs)

    async def cleanup(self):
        """Cleans up after the event loop is interupted."""
        await self.logger.debug("Cleaning up...", send=True)
        await super().logout()
        await self.db.close()
        await self.rabbit.close()

    async def on_ready(self):
        """Callback for when the bot is finished starting up."""
        self._startup_time = datetime.datetime.utcnow()

        await self.get_owner()

        await self.logger.debug("Online!", send=True)

    async def on_message(self, message):
        """Catches messages and acts appropriately.

        parameters:
            message (discord.Message): the message object
        """
        owner = await self.get_owner()

        if (
            owner
            and isinstance(message.channel, discord.DMChannel)
            and message.author.id != owner.id
            and not message.author.bot
        ):
            await owner.send(f'PM from `{message.author}`: "{message.content}"')

        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def on_error(self, event_method, *args, **kwargs):
        """Catches non-command errors and sends them to the error logger for processing.

        parameters:
            event_method (str): the event method name associated with the error (eg. on_message)
        """
        _, exception, _ = sys.exc_info()
        await self.logger.error(
            f"Bot error in {event_method}: {exception}", exception=exception
        )

    async def on_command_error(self, context, exception):
        """Catches command errors and sends them to the error logger for processing.

        parameters:
            context (discord.ext.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        await self.logger.error(
            f"Command error: {exception}", context=context, exception=exception
        )

    async def get_owner(self):
        """Gets the owner object from the bot application."""

        if not self.owner:
            try:
                await self.logger.debug("Looking up bot owner")
                app_info = await self.application_info()
                self.owner = app_info.owner
            except discord.errors.HTTPException:
                self.owner = None

        return self.owner

    async def can_run(self, ctx, *, call_once=False):
        """Wraps the default can_run check to evaluate if a check call is necessary.

        parameters:
            ctx (discord.ext.Context): the context associated with the command
            call_once (bool): True if the check should be retrieved from the call_once attribute
        """
        await self.logger.debug("Checking if command can run")

        is_bot_admin = await self.is_bot_admin(ctx)

        if is_bot_admin:
            return True

        # the user is not a bot admin, so they can't do this
        cog = getattr(ctx.command, "cog", None)
        if getattr(cog, "ADMIN_ONLY", False):
            # treat this as a command error to be caught by the dispatcher
            raise commands.MissingPermissions(["bot_admin"])

        result = await super().can_run(ctx, call_once=call_once)
        return result

    async def is_bot_admin(self, ctx):
        """Processes command context against admin/owner data.

        Command checks are disabled if the context author is the owner.

        They are also ignored if the author is bot admin in the config.

        parameters:
            ctx (discord.ext.Context): the context associated with the command
        """
        await self.logger.debug("Checking context against bot admins")

        owner = await self.get_owner()
        if getattr(owner, "id", None) == ctx.author.id:
            return True

        if ctx.message.author.id in [int(id) for id in self.config.main.admins.ids]:
            return True

        role_is_admin = False
        for role in getattr(ctx.message.author, "roles", []):
            if role.name in self.config.main.admins.roles:
                role_is_admin = True
                break
        if role_is_admin:
            return True

        return False

    async def reset_config_cache(self):
        """Deletes the guild config cache on a peridodic basis."""
        while True:
            self.config_cache = collections.defaultdict(dict)
            await asyncio.sleep(self.config.main.config_cache_reset)

    async def get_context_config(
        self, ctx, guild=None, create_if_none=True, get_from_cache=True
    ):
        """Gets the appropriate config for the context.

        parameters:
            ctx (discord.ext.Context): the context of the config
            guild (discord.Guild): the guild associated with the config
            create_if_none (bool): True if the config should be created if not found
            get_from_cache (bool): True if the config should be fetched from the cache
        """
        guild = guild or ctx.guild

        if get_from_cache:
            config = self.config_cache[guild.id]
            if config:
                return config

        lookup = guild.id if guild else "dmcontext"

        config = await self.guild_config_collection.find_one(
            {"guild_id": {"$eq": lookup}}
        )

        if not config and create_if_none:
            config = await self.create_new_context_config(lookup)
        else:
            config = await self.sync_config(config)

        return config

    async def create_new_context_config(self, lookup):
        """Creates a new guild config based on a lookup key (usually a guild ID).

        parameters:
            lookup (str): the primary key for the guild config document object
        """
        plugins_config = {}

        for plugin_name, plugin_data in self.plugin_api.plugins.items():
            plugins_config[plugin_name] = getattr(plugin_data, "config", {})

        config = munch.Munch()

        # pylint: disable=protected-access
        config._id = lookup
        config.guild_id = lookup
        config.command_prefix = self.config.main.default_prefix
        config.plugins = plugins_config

        await self.guild_config_collection.insert_one(config)

        return config

    async def sync_config(self, config):
        """Syncs the given config with the currently loaded plugins.

        parameters:
            config (dict): the guild config object
        """
        config = munch.munchify(config)

        for plugin_name, plugin_data in self.plugin_api.plugins.items():
            if not config.plugins.get(plugin_name):
                config.plugins[plugin_name] = getattr(plugin_data, "config", {})

        await self.guild_config_collection.replace_one(
            {"_id": config.get("_id")}, config
        )

        return config

    def generate_db_url(self, postgres=True):
        """Dynamically converts config to a Postgres/MongoDB url.

        parameters:
            postgres (bool): True if the URL for Postgres should be retrieved
        """
        db_type = "postgres" if postgres else "mongodb"

        try:
            config_child = getattr(self.config.main, db_type)

            user = config_child.user
            password = config_child.password

            name = getattr(config_child, "name") if postgres else None

            host = config_child.host
            port = config_child.port

        except AttributeError as exception:
            self.logger.console.warning(
                f"Could not generate DB URL for {db_type.upper()}: {exception}"
            )
            return None

        url = f"{db_type}://{user}:{password}@{host}:{port}"
        url_filtered = f"{db_type}://{user}:********@{host}:{port}"

        if name:
            url = f"{url}/{name}"

        # don't log the password
        self.logger.console.debug(f"Generated DB URL: {url_filtered}")

        return url

    async def get_postgres_ref(self):
        """Grabs the main DB reference.

        This doesn't follow a singleton pattern (use bot.db instead).
        """
        await self.logger.debug("Obtaining and binding to Gino instance")

        db_ref = gino.Gino()
        db_url = self.generate_db_url()
        await db_ref.set_bind(db_url)

        return db_ref

    def get_mongo_ref(self):
        """Grabs the MongoDB ref to the bot's configured table."""
        self.logger.console.debug("Obtaining MongoDB client")

        mongo_client = motor_asyncio.AsyncIOMotorClient(
            self.generate_db_url(postgres=False)
        )

        return mongo_client[self.config.main.mongodb.name]

    def generate_rabbit_url(self):
        """Dynamically converts config to an AMQP URL."""
        host = self.config.main.rabbitmq.host
        port = self.config.main.rabbitmq.port
        vhost = self.config.main.rabbitmq.vhost
        user = self.config.main.rabbitmq.user
        password = self.config.main.rabbitmq.password

        return f"amqp://{user}:{password}@{host}:{port}{vhost}"

    async def get_rabbit_connection(self):
        """Grabs the main RabbitMQ connection.

        This doesn't follow a singleton pattern (use bot.rabbit instead).
        """
        await self.logger.debug("Obtaining RabbitMQ robust instance")

        connection = await aio_pika.connect_robust(
            self.generate_rabbit_url(), loop=self.loop
        )

        return connection

    async def rabbit_publish(self, body, routing_key):
        """Publishes a body to the message queue.

        parameters:
            body (str): the body to send
            routing_key (str): the queue name to publish to
        """
        await self.logger.debug(f"RabbitMQ publish event to queue: {routing_key}")

        channel = await self.rabbit.channel()

        await channel.default_exchange.publish(
            aio_pika.Message(body=body.encode()), routing_key=routing_key
        )

        await channel.close()

    async def rabbit_consume(self, queue_name, handler, *args, **kwargs):
        """Consumes from a queue indefinitely.

        parameters:
            queue_name (str): the name of the queue
            handler (asyncio.coroutine): a handler for processing each message
            state_func (asyncio.coroutine): a state provider for exiting the consumation
            poll_wait (int): the time to wait inbetween each consumation
        """
        state_func = kwargs.pop("state_func", None)

        poll_wait = kwargs.pop("poll_wait", None)

        channel = await self.rabbit.channel()

        queue = await channel.declare_queue(queue_name, *args, **kwargs)

        state = True
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:

                if state_func:
                    state = await state_func()
                    if not state:
                        break

                if poll_wait:
                    await asyncio.sleep(poll_wait)

                async with message.process():
                    await self.logger.debug(
                        f"RabbitMQ consume event from queue: {queue_name}"
                    )
                    await handler(message.body.decode())

        await channel.close()

    def get_http_session(self):
        """Returns an async HTTP session."""
        return aiohttp.ClientSession()

    async def http_call(self, method, url, *args, **kwargs):
        """Makes an HTTP request.

        By default this returns JSON/dict with the status code injected.

        parameters:
            method (str): the HTTP method to use
            url (str): the URL to call
            get_raw_response (bool): True if the actual response object should be returned
        """
        client = self.get_http_session()

        method_fn = getattr(client, method.lower(), None)
        if not method_fn:
            raise AttributeError(f"Unable to use HTTP method: {method}")

        get_raw_response = kwargs.pop("get_raw_response", False)

        await self.logger.debug(f"Making HTTP {method.upper()} request to {url}")

        try:
            response_object = await method_fn(url, *args, **kwargs)

            if get_raw_response:
                response = response_object
            else:
                response = (
                    await munch.munchify(response_object.json())
                    if response_object
                    else munch.Munch()
                )
                response["status_code"] = getattr(response_object, "status_code", None)

        except Exception as exception:
            await self.logger.error(f"HTTP {method} call", exception=exception)
            response = {"status_code": None}

        await client.close()

        return response

    def process_plugin_setup(self, *args, **kwargs):
        """Provides a bot-level interface to loading a plugin.

        It is recommended to use this when setting up plugins.
        """
        return self.plugin_api.process_plugin_setup(*args, **kwargs)

    def get_logger(self, name):
        """Wraps getting a new logging channel.

        parameters:
            name (str): the name of the channel
        """
        return logger.BotLogger(self, name=name)

    @property
    def startup_time(self):
        """Gets the startup timestamp of the bot."""
        return self._startup_time
