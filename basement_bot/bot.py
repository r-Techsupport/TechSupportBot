"""The main bot functions.
"""

import asyncio
import sys

import admin
import aio_pika
import aiohttp
import discord
import embed
import error
import gino
import logger
import munch
import plugin
import yaml
from discord.ext import commands

log = logger.get_logger("Basement Bot")

#pylint: disable=too-many-public-methods
class BasementBot(commands.Bot):
    """The main bot object.

    parameters:
        run_on_init (bool): True if the bot should run on instantiation
        validate_config (bool): True if the bot's config should be validated
    """

    CONFIG_PATH = "./config.yaml"

    def __init__(self, run_on_init=True, validate_config=True):

        self.config = None
        self.load_config(validate=validate_config)

        self.db = None
        self.rabbit = None

        self.plugin_api = plugin.PluginAPI(bot=self)
        self.error_api = error.ErrorAPI(bot=self)
        self.embed_api = embed.EmbedAPI(bot=self)

        super().__init__(self.config.main.required.command_prefix)

        if run_on_init:
            log.debug("Bot starting upon init")
            self.run(self.config.main.required.auth_token)
        else:
            log.debug("Bot created but not started")

    async def on_ready(self):
        """Callback for when the bot is finished starting up."""
        game = self.config.main.optional.get("game")
        if game:
            await self.change_presence(activity=discord.Game(name=game))

        log.info(f"Commands available with the `{self.command_prefix}` prefix")

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
        """Catches non-command errors and sends them to the error API for processing.

        parameters:
            event_method (str): the event method name associated with the error (eg. on_message)
        """
        _, exception, _ = sys.exc_info()
        await self.error_api.handle_error(event_method, exception)

    async def on_command_error(self, context, exception):
        """Catches command errors and sends them to the error API for processing.

        parameters:
            context (discord.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        await self.error_api.handle_command_error(context, exception)

    def run(self, *args, **kwargs):
        """Starts the event loop and blocks until interrupted."""
        log.debug("Starting bot...")
        try:
            self.loop.run_until_complete(self.start(*args, **kwargs))
        except (SystemExit, KeyboardInterrupt):
            self.loop.run_until_complete(self.cleanup())
        finally:
            self.loop.close()

    async def start(self, *args, **kwargs):
        """Configures connections and then starts the actual bot."""
        try:
            self.db = await self.get_db_ref()
        except Exception as e:
            log.warning("Could not connect to Postgres - ignoring")

        try:
            self.rabbit = await self.get_rabbit_connection()
        except Exception as e:
            log.warning("Could not connect to RabbitMQ - ignoring")

        self.plugin_api.load_plugins()

        if self.db:
            await self.db.gino.create_all()

        try:
            self.add_cog(admin.AdminControl(self))
        except (TypeError, commands.CommandError) as e:
            log.warning(f"Could not load AdminControl cog: {e}")

        await super().start(*args, **kwargs)

    async def cleanup(self):
        """Cleans up after the event loop is interupted."""
        await super().logout()
        await self.db.close()
        await self.rabbit.close()

    async def get_owner(self):
        """Gets the owner object from the bot application."""
        try:
            app_info = await self.application_info()
            return app_info.owner
        except discord.errors.HTTPException:
            return None

    async def can_run(self, ctx, *, call_once=False):
        """Wraps the default can_run check to evaluate if a check call is necessary.

        parameters:
            ctx (discord.Context): the context associated with the command
            call_once (bool): True if the check should be retrieved from the call_once attribute
        """
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
            ctx (discord.Context): the context associated with the command
        """
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

    def load_config(self, validate):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH) as iostream:
            config = yaml.safe_load(iostream)
        self.config = munch.munchify(config)

        self.config.main.disabled_plugins = self.config.main.disabled_plugins or []

        if validate:
            self.validate_config()

    def validate_config(self):
        """Validates several config subsections."""
        for subsection in ["required"]:
            self.validate_config_subsection("main", subsection)

        for subsection in list(self.config.plugins.keys()):
            self.validate_config_subsection("plugins", subsection)

    def validate_config_subsection(self, section, subsection):
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
                if section == "plugins":
                    if not subsection in self.config.main.disabled_plugins:
                        # pylint: disable=line-too-long
                        log.warning(
                            f"Disabling loading of plugin {subsection} due to missing config key {error_key}"
                        )
                        # disable the plugin if we can't get its config
                        self.config.main.disabled_plugins.append(subsection)
                else:
                    raise ValueError(
                        f"Config key {error_key} from {section}.{subsection} not supplied"
                    )

    def generate_db_url(self):
        """Dynamically converts config to a Postgres URL."""
        try:
            user = self.config.main.database.user
            password = self.config.main.database.password
            name = self.config.main.database.name
            host = self.config.main.database.host
            port = self.config.main.database.port
        except AttributeError:
            return None

        return f"postgres://{user}:{password}@{host}:{port}/{name}"

    async def get_db_ref(self):
        """Grabs the main DB reference.

        This doesn't follow a singleton pattern (use bot.db instead).
        """
        db_ref = gino.Gino()
        db_url = self.generate_db_url()
        await db_ref.set_bind(db_url)

        return db_ref

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
                    await handler(message.body.decode())

        await channel.close()

    def get_http_session(self):
        """Returns an async HTTP session."""
        return aiohttp.ClientSession()

    async def http_call(self, method, *args, **kwargs):
        """Makes an HTTP request.

        By default this returns JSON/dict with the status code injected.

        parameters:
            method (string): the HTTP method to use
            get_raw_response (bool): True if the actual response object should be returned
        """
        client = self.get_http_session()

        method_fn = getattr(client, method.lower(), None)
        if not method_fn:
            raise AttributeError(f"Unable to use HTTP method: {method}")

        get_raw_response = kwargs.pop("get_raw_response", False)

        try:
            response_object = await method_fn(*args, **kwargs)

            if get_raw_response:
                return response_object

            response = await response_object.json() if response_object else {}
            response["status_code"] = getattr(response_object, "status_code", None)

        except Exception as e:
            await self.error_api.handle_error("http_call", e)
            response = {"status_code": None}

        await client.close()

        return response
