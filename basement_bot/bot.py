"""The main bot functions.
"""

# import ast
import asyncio
import collections
import datetime
import json
import re
import sys

import admin
import aio_pika
import aiohttp
import config
import discord
import embeds as embed_package
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
        self.embed_api = embed_package.EmbedAPI(bot=self)

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
            config_ = yaml.safe_load(iostream)

        self.config = munch.munchify(config_)

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

        await self.logger.debug("Loading Admin commands...")
        try:
            self.add_cog(admin.AdminControl(self))
        except Exception as exception:
            await self.logger.warning(f"Could not add Admin commands: {exception}")

        await self.logger.debug("Loading Config commands...")
        try:
            self.add_cog(config.ConfigControl(self))
        except Exception as exception:
            await self.logger.warning(f"Could not load Config commands: {exception}")

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
            f"Bot error in {event_method}: {exception}",
            exception=exception,
        )

    async def on_command_error(self, context, exception):
        """Catches command errors and sends them to the error logger for processing.

        parameters:
            context (discord.ext.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        config_ = await self.get_context_config(context)

        await self.logger.debug("Checking config for log channel")
        channel = config_.get("log_channel")

        await self.logger.error(
            f"Command error: {exception}",
            context=context,
            exception=exception,
            channel=channel,
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
        """Wraps the default can_run check to evaluate bot-admin permission.

        parameters:
            ctx (discord.ext.Context): the context associated with the command
            call_once (bool): True if the check should be retrieved from the call_once attribute
        """
        await self.logger.debug("Checking if command can run")

        is_bot_admin = await self.is_bot_admin(ctx)

        cog = getattr(ctx.command, "cog", None)
        if getattr(cog, "ADMIN_ONLY", False) and not is_bot_admin:
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
            await self.logger.debug("Resetting guild config cache")
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
        guild = guild or getattr(ctx, "guild", None)

        lookup = guild.id if guild else "dmcontext"

        await self.logger.debug(f"Getting config for lookup key: {lookup}")

        if get_from_cache:
            config_ = self.config_cache[lookup]
            if config_:
                return config_

        config_ = await self.guild_config_collection.find_one(
            {"guild_id": {"$eq": lookup}}
        )

        if not config_ and create_if_none:
            await self.logger.debug("No config found in MongoDB")
            config_ = await self.create_new_context_config(lookup)
        elif config_:
            config_ = await self.sync_config(config_)

        return config_

    async def create_new_context_config(self, lookup):
        """Creates a new guild config based on a lookup key (usually a guild ID).

        parameters:
            lookup (str): the primary key for the guild config document object
        """

        plugins_config = {}

        await self.logger.debug("Evaluating plugin data")
        for plugin_name, plugin_data in self.plugin_api.plugins.items():
            plugins_config[plugin_name] = getattr(plugin_data, "config", {})

        config_ = munch.Munch()

        # pylint: disable=protected-access
        config_._id = lookup
        config_.guild_id = lookup
        config_.command_prefix = self.config.main.default_prefix
        config_.plugins = plugins_config
        config_.log_channel = None

        try:
            await self.logger.debug(f"Inserting new config for lookup key: {lookup}")
            await self.guild_config_collection.insert_one(config_)
        except Exception as exception:
            await self.logger.error(
                "Could not insert guild config into MongoDB",
                exception=exception,
                send=False,
            )

        return config_

    async def sync_config(self, config_object):
        """Syncs the given config with the currently loaded plugins.

        parameters:
            config (dict): the guild config object
        """
        config_object = munch.munchify(config_object)

        should_update = False

        await self.logger.debug("Evaluating plugin data")
        for plugin_name, plugin_data in self.plugin_api.plugins.items():
            plugin_config = config_object.plugins.get(plugin_name)
            plugin_config_from_data = getattr(plugin_data, "config", {})

            if not plugin_config and plugin_config_from_data:
                should_update = True

                await self.logger.debug(
                    f"Found plugin {plugin_name} not in config with ID {config_object.guild_id}"
                )
                config_object.plugins[plugin_name] = plugin_config_from_data

        if should_update:
            await self.logger.debug(
                f"Updating guild config for lookup key: {config_object.guild_id}"
            )
            await self.guild_config_collection.replace_one(
                {"_id": config_object.get("_id")}, config_object
            )

        return config_object

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

        rabbit_url = f"amqp://{user}:{password}@{host}:{port}{vhost}"
        rabbit_url_filtered = f"amqp://{user}:********@{host}:{port}{vhost}"

        self.logger.console.debug(f"Generated RabbitMQ URL: {rabbit_url_filtered}")

        return rabbit_url

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
        self.logger.console.debug("Generating HTTP Client object")
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

    async def tagged_response(self, ctx, content=None, target=None, **kwargs):
        """Sends a context response with the original author tagged.

        parameters:
            ctx (discord.ext.Context): the context object
            content (str): the message to send
            target (discord.Member): the Discord user to tag
        """
        user_mention = target.mention if target else ctx.message.author.mention
        content = f"{user_mention} {content}" if content else user_mention

        message = await ctx.send(content=content, **kwargs)
        return message

    def get_guild_from_channel_id(self, channel_id):
        """Helper for getting the guild associated with a channel.

        parameters:
            bot (BasementBot): the bot object
            channel_id (Union[string, int]): the unique ID of the channel
        """
        self.logger.console.debug(f"Getting guild from channel ID: {channel_id}")
        for guild in self.guilds:
            for channel in guild.channels:
                if channel.id == int(channel_id):
                    self.logger.console.debug(
                        f"Found guild ID {guild.id} associated with channel ID: {channel_id}"
                    )
                    return guild

        self.logger.console.debug(
            f"Could not find guild ID associated with channel ID: {channel_id}"
        )
        return None

    def sub_mentions_for_usernames(self, content):
        """Subs a string of Discord mentions with the corresponding usernames.

        parameters:
            bot (BasementBot): the bot object
            content (str): the content to parse
        """

        def get_nick_from_id_match(match):
            id_ = int(match.group(1))
            user = self.get_user(id_)
            return f"@{user.name}" if user else "@user"

        self.logger.console.debug("Subbing mention texts with usernames")

        return re.sub(r"<@?!?(\d+)>", get_nick_from_id_match, content)

    async def get_json_from_attachment(
        self, message, as_string=False, allow_failure=True
    ):
        """Returns a JSON object parsed from a message's attachment.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            message (Message): the message object
        """
        data = None

        await self.logger.debug(f"Checking message ID: {message.id} for attachments")
        if message.attachments:
            await self.logger.debug(
                f"Parsing JSON from upload associated with message ID: {message.id}"
            )
            try:
                json_bytes = await message.attachments[0].read()
                json_str = json_bytes.decode("UTF-8")
                # hehehe munch ~~O< oooo
                # data = munch.munchify(ast.literal_eval(json_str))
                data = munch.munchify(json.loads(json_str))
                if as_string:
                    data = json.dumps(data)
            # this could probably be more specific
            except Exception as exception:
                await self.logger.error(
                    f"Could not parse JSON from file: {exception}", send=False
                )
                if not allow_failure:
                    raise exception

        return data

    # pylint: disable=too-many-branches, too-many-arguments
    async def paginate(self, ctx, embeds, timeout=300, tag_user=False, restrict=False):
        """Paginates a set of embed objects for users to sort through

        parameters:
            ctx (discord.ext.Context): the context object for the message
            embeds (Union[discord.Embed, str][]): the embeds (or URLs to render them) to paginate
            timeout (int) (seconds): the time to wait before exiting the reaction listener
            tag_user (bool): True if the context user should be mentioned in the response
            restrict (bool): True if only the caller and admins can navigate the pages
        """
        # limit large outputs
        embeds = embeds[:20]

        for index, embed in enumerate(embeds):
            if isinstance(embed, self.embed_api.Embed):
                embed.set_footer(text=f"Page {index+1} of {len(embeds)}")

        index = 0
        get_args = lambda index: {
            "content": embeds[index]
            if not isinstance(embeds[index], self.embed_api.Embed)
            else None,
            "embed": embeds[index]
            if isinstance(embeds[index], self.embed_api.Embed)
            else None,
        }

        if tag_user:
            message = await self.tagged_response(ctx, **get_args(index))
        else:
            message = await ctx.send(**get_args(index))

        if isinstance(ctx.channel, discord.DMChannel):
            return

        start_time = datetime.datetime.now()

        for unicode_reaction in ["\u25C0", "\u25B6", "\u26D4", "\U0001F5D1"]:
            await message.add_reaction(unicode_reaction)

        await self.logger.debug(f"Starting pagination loop with {len(embeds)} pages")
        while True:
            if (datetime.datetime.now() - start_time).seconds > timeout:
                break

            try:
                reaction, user = await ctx.bot.wait_for(
                    "reaction_add", timeout=timeout, check=lambda r, u: not bool(u.bot)
                )
            # this seems to raise an odd timeout error, for now just catch-all
            except Exception:
                break

            # check if the reaction should be processed
            if (reaction.message.id != message.id) or (
                restrict and user.id != ctx.author.id
            ):
                # this is checked first so it can pass to the deletion
                pass

            # move forward
            elif str(reaction) == "\u25B6" and index < len(embeds) - 1:
                index += 1
                await message.edit(**get_args(index))

            # move backward
            elif str(reaction) == "\u25C0" and index > 0:
                index -= 1
                await message.edit(**get_args(index))

            # stop pagination
            elif str(reaction) == "\u26D4" and user.id == ctx.author.id:
                await self.logger.debug("Stopping pagination message at user request")
                break

            # delete embed
            elif str(reaction) == "\U0001F5D1" and user.id == ctx.author.id:
                await self.logger.debug("Deleting pagination message at user request")
                await message.delete()
                break

            try:
                await reaction.remove(user)
            except discord.Forbidden:
                await self.logger.error(
                    "Could not delete user reaction on pagination message", send=False
                )

        try:
            await message.clear_reactions()
        except (discord.Forbidden, discord.NotFound):
            await self.logger.error(
                "Could not delete all reactions on pagination message", send=False
            )

    def task_paginate(self, *args, **kwargs):
        """Creates a pagination task.

        This is useful if you want your command to finish executing when pagination starts.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            *args (...list): the args with which to call the pagination method
            **kwargs (...dict): the keyword args with which to call the pagination method
        """
        self.loop.create_task(self.paginate(*args, **kwargs))

    @property
    def startup_time(self):
        """Gets the startup timestamp of the bot."""
        return self._startup_time
