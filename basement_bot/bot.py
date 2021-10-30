"""The main bot functions.
"""

import asyncio
import collections
import datetime
import inspect
import os
import re
import sys

import admin
import aio_pika
import botlog
import config
import discord
import error
import gino
import help as help_commands
import ipc as ipc_local
import munch
import plugin
import raw
import util
import yaml
from discord.ext import commands, ipc
from motor import motor_asyncio


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class BasementBot(commands.Bot):
    """The main bot object.

    parameters:
        run_on_init (bool): True if the bot should run on instantiation
    """

    CONFIG_PATH = "./config.yml"
    GUILD_CONFIG_COLLECTION = "guild_config"
    IPC_SECRET_ENV_KEY = "IPC_SECRET"
    CONFIRM_YES_EMOJI = "✅"
    CONFIRM_NO_EMOJI = "❌"
    PAGINATE_LEFT_EMOJI = "⬅️"
    PAGINATE_RIGHT_EMOJI = "➡️"
    PAGINATE_STOP_EMOJI = "⏹️"
    PAGINATE_DELETE_EMOJI = "🗑️"

    PluginConfig = plugin.PluginConfig

    def __init__(self, run_on_init=True, intents=None, allowed_mentions=None):
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            allowed_mentions=allowed_mentions,
        )

        self.owner = None
        self.config = None
        self.mongo = None
        self.db = None
        self.rabbit = None
        self._startup_time = None
        self.guild_config_collection = None
        self.config_cache = collections.defaultdict(dict)
        self.config_lock = asyncio.Lock()
        self.ipc = None

        self.load_bot_config(validate=True)

        self.builtin_cogs = []
        self.plugin_api = plugin.PluginAPI(bot=self)

        self.logger = botlog.BotLogger(
            bot=self,
            name=self.__class__.__name__,
            queue_wait=self.config.main.logging.queue_wait_seconds,
            send=not self.config.main.logging.block_discord_send,
        )

        if not run_on_init:
            return

        self.run(self.config.main.auth_token)

    def load_bot_config(self, validate):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH, encoding="utf8") as iostream:
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
        guild_config = await self.get_context_config(guild=message.guild)
        return getattr(guild_config, "command_prefix", self.config.main.default_prefix)

    def run(self, *args, **kwargs):
        """Starts IPC and the event loop and blocks until interrupted."""
        if os.getenv(self.IPC_SECRET_ENV_KEY):
            self.logger.console.debug("Setting up IPC server")
            self.ipc = ipc.Server(
                self, host="0.0.0.0", secret_key=os.getenv(self.IPC_SECRET_ENV_KEY)
            )
            self.ipc.start()
        else:
            self.logger.console.debug("No IPC secret found in env - ignoring IPC setup")

        try:
            self.loop.run_until_complete(self.start(*args, **kwargs))
        except (SystemExit, KeyboardInterrupt):
            self.loop.run_until_complete(self.cleanup())
        finally:
            self.loop.close()

    # pylint: disable=too-many-statements
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

        await self.logger.debug("Loading Help commands...")
        self.remove_command("help")
        help_cog = help_commands.Helper(self)
        self.add_cog(help_cog)

        await self.load_builtin_cog(admin.AdminControl)
        await self.load_builtin_cog(config.ConfigControl)
        await self.load_builtin_cog(raw.Raw)

        if self.ipc:
            await self.logger.debug("Loading IPC endpoints...")
            try:
                self.add_cog(ipc_local.IPCEndpoints(self))
            except Exception as exception:
                await self.logger.warning(f"Could not load IPC endpoints: {exception}")

        await self.logger.debug("Logging into Discord...")
        await super().start(*args, **kwargs)

    async def load_builtin_cog(self, cog):
        """Loads a cog as a builtin.

        parameters:
            cog (discord.commands.ext.Cog): the cog to load
        """
        try:
            cog = cog(self)
            self.add_cog(cog)
            self.builtin_cogs.append(cog.qualified_name)
        except Exception as exception:
            await self.logger.warning(
                f"Could not load builtin cog {cog.__name__}: {exception}"
            )

    async def cleanup(self):
        """Cleans up after the event loop is interupted."""
        await self.logger.debug("Cleaning up...", send=True)
        await super().logout()
        await self.rabbit.close()

    async def on_ready(self):
        """Callback for when the bot is finished starting up."""
        self._startup_time = datetime.datetime.utcnow()

        await self.logger.event("ready")

        await self.get_owner()

        await self.logger.debug("Online!", send=True)

    async def on_message(self, message):
        """Catches messages and acts appropriately.

        parameters:
            message (discord.Message): the message object
        """
        await self.logger.event("message", message=message)

        owner = await self.get_owner()

        if (
            owner
            and isinstance(message.channel, discord.DMChannel)
            and message.author.id != owner.id
            and not message.author.bot
        ):
            await self.logger.info(
                f'PM from `{message.author}`: "{message.content}"', send=True
            )

        await self.process_commands(message)

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
        if self.extra_events.get("on_command_error", None):
            return
        if hasattr(context.command, "on_error"):
            return
        if context.cog:
            # pylint: disable=protected-access
            if (
                commands.Cog._get_overridden_method(context.cog.cog_command_error)
                is not None
            ):
                return

        message_template = error.COMMAND_ERROR_RESPONSE_TEMPLATES.get(
            exception.__class__, ""
        )
        # see if we have mapped this error to no response (None)
        # or if we have added it to the global ignore list of errors
        if message_template is None or exception.__class__ in error.IGNORED_ERRORS:
            return
        # otherwise set it a default error message
        if message_template == "":
            message_template = error.ErrorResponse()

        error_message = message_template.get_message(exception)

        await context.send(f"{context.author.mention} {error_message}")

        log_channel = await self.get_log_channel_from_guild(
            getattr(context, "guild", None), key="logging_channel"
        )
        await self.logger.error(
            f"Command error: {exception}",
            exception=exception,
            channel=log_channel,
        )

    async def on_ipc_error(self, _endpoint, exception):
        """Catches IPC errors and sends them to the error logger for processing.

        parameters:
            endpoint (str): the endpoint called
            exception (Exception): the exception object associated with the error
        """
        await self.logger.error(
            f"IPC error: {exception}", exception=exception, send=True
        )

    async def on_guild_join(self, guild):
        """Configures a new guild upon joining.

        parameters:
            guild (discord.Guild): the guild that was joined
        """
        for cog in self.cogs.values():
            if getattr(cog, "COG_TYPE", "").lower() == "loop":
                await cog.register_new_tasks(guild)

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_join", guild=guild, send=True, channel=log_channel
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

        if is_bot_admin:
            result = True
        else:
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
        """Deletes the guild config cache on a periodic basis."""
        while True:
            await self.logger.debug("Resetting guild config cache")
            self.config_cache = collections.defaultdict(dict)
            await asyncio.sleep(self.config.main.config_cache_reset)

    async def get_context_config(
        self, ctx=None, guild=None, create_if_none=True, get_from_cache=True
    ):
        """Gets the appropriate config for the context.

        parameters:
            ctx (discord.ext.Context): the context of the config
            guild (discord.Guild): the guild associated with the config (provided instead of ctx)
            create_if_none (bool): True if the config should be created if not found
            get_from_cache (bool): True if the config should be fetched from the cache
        """
        if ctx:
            guild_from_ctx = getattr(ctx, "guild", None)
            lookup = guild_from_ctx.id if guild_from_ctx else "dmcontext"
        elif guild:
            lookup = guild.id
        else:
            return None

        lookup = str(lookup)

        await self.logger.debug(f"Getting config for lookup key: {lookup}")

        # locking prevents duplicate configs being made
        async with self.config_lock:
            if get_from_cache:
                config_ = self.config_cache[lookup]
                if config_:
                    return config_

            config_ = await self.guild_config_collection.find_one(
                {"guild_id": {"$eq": lookup}}
            )

            if not config_:
                await self.logger.debug("No config found in MongoDB")
                if create_if_none:
                    config_ = await self.create_new_context_config(lookup)
            else:
                config_ = await self.sync_config(config_)

            if config_:
                self.config_cache[lookup] = config_

        return config_

    async def get_log_channel_from_guild(self, guild, key):
        """Gets the log channel ID associated with the given guild.

        This also checks if the channel exists in the correct guild.

        parameters:
            guild (discord.Guild): the guild object to reference
            key (string): the key to use when looking up the channel
        """
        if not guild:
            return None

        config_ = await self.get_context_config(guild=guild)
        channel_id = config_.get(key)

        if not channel_id:
            return None

        if not guild.get_channel(int(channel_id)):
            return None

        return channel_id

    async def guild_log(self, guild, key, log_type, message, **kwargs):
        """Shortcut wrapper for directly to a guild's log channel.

        parameters:
            guild (discord.Guild): the guild object to reference
            key (string): the key to use when looking up the channel
            log_type (string): the log type to use (info, error, warning, etc.)
            message (string): the log message
        """
        log_channel = await self.get_log_channel_from_guild(guild, key)
        await getattr(self.logger, log_type)(message, channel=log_channel, **kwargs)

    async def create_new_context_config(self, lookup):
        """Creates a new guild config based on a lookup key (usually a guild ID).

        parameters:
            lookup (str): the primary key for the guild config document object
        """

        plugins_config = {}

        await self.logger.debug("Evaluating plugin data")
        for plugin_name, plugin_data in self.plugin_api.plugins.items():
            plugin_config = getattr(plugin_data, "fallback_config", {})
            if plugin_config:
                # don't attach to guild config if plugin isn't configurable
                plugins_config[plugin_name] = plugin_config

        config_ = munch.Munch()

        config_.guild_id = str(lookup)
        config_.command_prefix = self.config.main.default_prefix
        config_.logging_channel = None
        config_.member_events_channel = None
        config_.guild_events_channel = None
        config_.private_channels = []

        config_.plugins = plugins_config

        try:
            await self.logger.debug(f"Inserting new config for lookup key: {lookup}")
            await self.guild_config_collection.insert_one(config_)
        except Exception as exception:
            # safely finish because the new config is still useful
            await self.logger.error(
                "Could not insert guild config into MongoDB", exception=exception
            )

        return config_

    async def sync_config(self, config_object):
        """Syncs the given config with the currently loaded plugins.

        parameters:
            config_object (dict): the guild config object
        """
        config_object = munch.munchify(config_object)

        should_update = False

        await self.logger.debug("Evaluating plugin data")
        for plugin_name, plugin_data in self.plugin_api.plugins.items():
            plugin_config = config_object.plugins.get(plugin_name)
            plugin_config_from_data = getattr(plugin_data, "fallback_config", {})

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

        db_ref.Model.__table_args__ = {"extend_existing": True}

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
        channel = await self.rabbit.channel()

        await self.logger.debug(f"RabbitMQ publish event to queue: {routing_key}")
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

        await self.logger.debug(f"Declaring queue: {queue_name}")
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

    # pylint: disable=too-many-branches, too-many-arguments
    async def paginate(self, ctx, embeds, timeout=300, tag_user=False, restrict=False):
        """Paginates a set of embed objects for users to sort through

        parameters:
            ctx (discord.ext.Context): the context object for the message
            embeds (Union[discord.Embed, str][]): the embeds (or URLs to render them) to paginate
            timeout (int) (seconds): the time to wait before exiting the reaction listener
            tag_user (bool): True if the context user should be mentioned in the response
            restrict (bool): True if only the caller can navigate the results
        """
        # limit large outputs
        embeds = embeds[:20]

        for index, embed in enumerate(embeds):
            if isinstance(embed, discord.Embed):
                embed.set_footer(text=f"Page {index+1} of {len(embeds)}")

        index = 0
        get_args = lambda index: {
            "content": embeds[index]
            if not isinstance(embeds[index], discord.Embed)
            else None,
            "embed": embeds[index]
            if isinstance(embeds[index], discord.Embed)
            else None,
        }

        if tag_user:
            message = await util.send_with_mention(ctx, **get_args(index))
        else:
            message = await ctx.send(**get_args(index))

        if isinstance(ctx.channel, discord.DMChannel):
            return

        start_time = datetime.datetime.now()

        for unicode_reaction in [
            self.PAGINATE_LEFT_EMOJI,
            self.PAGINATE_RIGHT_EMOJI,
            self.PAGINATE_STOP_EMOJI,
            self.PAGINATE_DELETE_EMOJI,
        ]:
            await message.add_reaction(unicode_reaction)

        await self.logger.debug(f"Starting pagination loop with {len(embeds)} pages")
        while True:
            if (datetime.datetime.now() - start_time).seconds > timeout:
                break

            try:
                reaction, user = await self.wait_for(
                    "reaction_add",
                    timeout=timeout,
                    check=lambda r, u: not bool(u.bot) and r.message.id == message.id,
                )
            # this seems to raise an odd timeout error, for now just catch-all
            except Exception:
                break

            if restrict and user.id != ctx.author.id:
                # this is checked first so it can pass to the deletion
                pass

            # move forward
            elif str(reaction) == self.PAGINATE_RIGHT_EMOJI and index < len(embeds) - 1:
                index += 1
                await message.edit(**get_args(index))

            # move backward
            elif str(reaction) == self.PAGINATE_LEFT_EMOJI and index > 0:
                index -= 1
                await message.edit(**get_args(index))

            # stop pagination
            elif str(reaction) == self.PAGINATE_STOP_EMOJI:
                await self.logger.debug("Stopping pagination message at user request")
                break

            # delete embed
            elif str(reaction) == self.PAGINATE_DELETE_EMOJI:
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
        except discord.NotFound:
            pass

    def task_paginate(self, *args, **kwargs):
        """Creates a pagination task from the given args.

        This is useful if you want your command to finish executing when pagination starts.
        """
        self.loop.create_task(self.paginate(*args, **kwargs))

    async def confirm(self, ctx, title, timeout=60, delete_after=False, bypass=None):
        """Waits on a confirm reaction from a given user.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            title (str): the message content to which the user reacts
            timeout (int): the number of seconds before timing out
            delete_after (bool): True if the confirmation message should be deleted
            bypass (list[discord.Role]): the list of roles able to confirm (empty by default)
        """
        if bypass is None:
            bypass = []

        message = await util.send_with_mention(ctx, content=title, target=ctx.author)
        await message.add_reaction(self.CONFIRM_YES_EMOJI)
        await message.add_reaction(self.CONFIRM_NO_EMOJI)

        result = False
        while True:
            try:
                reaction, user = await self.wait_for(
                    "reaction_add",
                    timeout=timeout,
                    check=lambda r, u: not bool(u.bot) and r.message.id == message.id,
                )
            except Exception:
                break

            member = ctx.guild.get_member(user.id)
            if not member:
                pass

            elif user.id != ctx.author.id and not any(
                role in getattr(member, "roles", []) for role in bypass
            ):
                pass

            elif str(reaction) == self.CONFIRM_YES_EMOJI:
                result = True
                break

            elif str(reaction) == self.CONFIRM_NO_EMOJI:
                break

            try:
                await reaction.remove(user)
            except discord.Forbidden:
                await self.logger.error(
                    "Could not delete user reaction on confirmation message", send=False
                )

        if delete_after:
            await message.delete()

        return result

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

        return re.sub(r"<@?!?(\d+)>", get_nick_from_id_match, content)

    def process_plugin_setup(self, *args, **kwargs):
        """Provides a bot-level interface to loading a plugin.

        It is recommended to use this when setting up plugins.
        """
        return self.plugin_api.process_plugin_setup(*args, **kwargs)

    def preserialize_object(self, obj):
        """Provides sane object -> dict transformation for most objects.

        This is primarily used to send Discord.py object data via the IPC server.

        parameters;
            obj (object): the object to serialize
        """
        attributes = inspect.getmembers(obj, lambda a: not inspect.isroutine(a))
        filtered_attributes = filter(
            lambda e: not (e[0].startswith("__") and e[0].endswith("__")), attributes
        )

        data = {}
        for name, attr in filtered_attributes:
            # remove single underscores
            if name.startswith("_"):
                name = name[1:]

            # if it's not a basic type, stringify it
            # only catch: nested data is not readily JSON
            if isinstance(attr, list):
                attr = [str(element) for element in attr]
            elif isinstance(attr, dict):
                attr = {str(key): str(value) for key, value in attr.items()}
            elif isinstance(attr, int):
                attr = str(attr)
            elif isinstance(attr, float):
                pass
            else:
                attr = str(attr)

            data[str(name)] = attr

        return data

    @property
    def startup_time(self):
        """Gets the startup timestamp of the bot."""
        return self._startup_time

    async def on_command(self, ctx):
        """See: https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.on_command"""
        config_ = await self.get_context_config(ctx)
        if str(ctx.channel.id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            getattr(ctx, "guild", None), key="logging_channel"
        )
        await self.logger.event("command", context=ctx, send=True, channel=log_channel)

    async def on_connect(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_connect"""
        await self.logger.event("connected")

    async def on_resumed(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_resumed"""
        await self.logger.event("resumed")

    async def on_disconnect(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_disconnect"""
        await self.logger.event("disconnected")

    async def on_message_delete(self, message):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_delete"""
        guild = getattr(message.channel, "guild", None)
        channel_id = getattr(message.channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "message_delete", message=message, send=True, channel=log_channel
        )

    async def on_bulk_message_delete(self, messages):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_bulk_message_delete"""
        guild = getattr(messages[0].channel, "guild", None)
        channel_id = getattr(messages[0].channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "bulk_message_delete", messages=messages, send=True, channel=log_channel
        )

    async def on_message_edit(self, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_edit"""
        guild = getattr(before.channel, "guild", None)
        channel_id = getattr(before.channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        # this seems to spam, not sure why
        if before.content == after.content:
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "message_edit", before=before, after=after, send=True, channel=log_channel
        )

    async def on_reaction_add(self, reaction, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_add"""
        guild = getattr(reaction.message.channel, "guild", None)
        channel_id = getattr(reaction.message.channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "reaction_add", reaction=reaction, user=user, send=True, channel=log_channel
        )

    async def on_reaction_remove(self, reaction, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_remove"""
        guild = getattr(reaction.message.channel, "guild", None)
        channel_id = getattr(reaction.message.channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "reaction_remove",
            reaction=reaction,
            user=user,
            send=True,
            channel=log_channel,
        )

    async def on_reaction_clear(self, message, reactions):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_clear"""
        guild = getattr(message.channel, "guild", None)
        channel_id = getattr(message.channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "reaction_clear",
            message=message,
            reactions=reactions,
            send=True,
            channel=log_channel,
        )

    async def on_reaction_clear_emoji(self, reaction):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_clear_emoji"""
        guild = getattr(reaction.message.channel, "guild", None)
        channel_id = getattr(reaction.message.channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            getattr(reaction.message, "guild", None), key="guild_events_channel"
        )
        await self.logger.event(
            "reaction_clear_emoji", reaction=reaction, send=True, channel=log_channel
        )

    async def on_guild_channel_delete(self, channel):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_delete"""
        log_channel = await self.get_log_channel_from_guild(
            getattr(channel, "guild", None), key="guild_events_channel"
        )
        await self.logger.event(
            "guild_channel_delete", channel_=channel, send=True, channel=log_channel
        )

    async def on_guild_channel_create(self, channel):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_create"""
        log_channel = await self.get_log_channel_from_guild(
            getattr(channel, "guild", None), key="guild_events_channel"
        )
        await self.logger.event(
            "guild_channel_create", channel_=channel, send=True, channel=log_channel
        )

    async def on_guild_channel_update(self, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_update"""
        guild = getattr(before, "guild", None)
        channel_id = getattr(before, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_channel_update",
            before=before,
            after=after,
            send=True,
            channel=log_channel,
        )

    async def on_guild_channel_pins_update(self, channel, last_pin):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_pins_update"""
        guild = getattr(channel, "guild", None)
        channel_id = getattr(channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_channel_pins_update",
            channel_=channel,
            last_pin=last_pin,
            send=True,
            channel=log_channel,
        )

    async def on_guild_integrations_update(self, guild):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_integrations_update"""
        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_integrations_update", guild=guild, send=True, channel=log_channel
        )

    async def on_webhooks_update(self, channel):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_webhooks_update"""
        guild = getattr(channel, "guild", None)
        channel_id = getattr(channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "webhooks_update", channel_=channel, send=True, channel=log_channel
        )

    async def on_member_join(self, member):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join"""
        log_channel = await self.get_log_channel_from_guild(
            getattr(member, "guild", None), key="member_events_channel"
        )
        await self.logger.event(
            "member_join", member=member, send=True, channel=log_channel
        )

    async def on_member_remove(self, member):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_remove"""
        log_channel = await self.get_log_channel_from_guild(
            getattr(member, "guild", None), key="member_events_channel"
        )
        await self.logger.event(
            "member_remove", member=member, send=True, channel=log_channel
        )

    async def on_guild_remove(self, guild):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_remove"""
        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_remove", guild=guild, send=True, channel=log_channel
        )

    async def on_guild_update(self, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_update"""
        log_channel = await self.get_log_channel_from_guild(
            before, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_update", before=before, after=after, send=True, channel=log_channel
        )

    async def on_guild_role_create(self, role):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_create"""
        log_channel = await self.get_log_channel_from_guild(
            role.guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_role_create", role=role, send=True, channel=log_channel
        )

    async def on_guild_role_delete(self, role):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_delete"""
        log_channel = await self.get_log_channel_from_guild(
            role.guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_role_delete", role=role, send=True, channel=log_channel
        )

    async def on_guild_role_update(self, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_update"""
        log_channel = await self.get_log_channel_from_guild(
            before.guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_role_update",
            before=before,
            after=after,
            send=True,
            channel=log_channel,
        )

    async def on_guild_emojis_update(self, guild, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_emojis_update"""
        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.event(
            "guild_emojis_update",
            guild=guild,
            before=before,
            after=after,
            send=True,
            channel=log_channel,
        )

    async def on_guild_available(self, guild):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_available"""
        await self.logger.event("guild_available", guild=guild, send=True)

    async def on_guild_unavailable(self, guild):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_unavailable"""
        await self.logger.event("guild_unavailable", guild=guild, send=True)

    async def on_member_ban(self, guild, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_ban"""
        log_channel = await self.get_log_channel_from_guild(
            guild, key="member_events_channel"
        )
        await self.logger.event(
            "member_ban", guild=guild, user=user, send=True, channel=log_channel
        )

    async def on_member_unban(self, guild, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_unban"""
        log_channel = await self.get_log_channel_from_guild(
            guild, key="member_events_channel"
        )
        await self.logger.event(
            "member_unban", guild=guild, user=user, send=True, channel=log_channel
        )

    async def on_invite_create(self, invite):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_invite_create"""
        await self.logger.event("invite_create", invite=invite, send=True)

    async def on_invite_delete(self, invite):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_invite_delete"""
        await self.logger.event("invite_delete", invite=invite, send=True)

    async def on_group_join(self, channel, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_group_join"""
        await self.logger.event("group_join", channel=channel, user=user, send=True)

    async def on_group_remove(self, channel, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_group_remove"""
        await self.logger.event("group_remove", channel=channel, user=user, send=True)

    async def on_relationship_add(self, relationship):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_relationship_add"""
        await self.logger.event(
            "relationship_add", relationship=relationship, send=True
        )

    async def on_relationship_remove(self, relationship):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_relationship_remove"""
        await self.logger.event(
            "relationship_remove", relationship=relationship, send=True
        )

    async def on_relationship_update(self, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_relationship_update"""
        await self.logger.event(
            "relationship_update", before=before, after=after, send=True
        )
