"""The main bot functions.
"""

import asyncio
import datetime
import glob
import json
import os
import threading

import botlogging
import discord
import expiringdict
import gino
import ircrelay
import munch
import yaml
from botlogging import LogContext, LogLevel
from core import auxiliary, custom_errors, databases, http
from discord import app_commands
from discord.ext import commands


class ExtensionConfig:
    """Represents the config of an extension."""

    def __init__(self):
        self.data = munch.DefaultMunch(None)

    def add(self, key, datatype, title, description, default):
        """Adds a new entry to the config.

        This is usually used in the extensions's setup function.

        parameters:
            key (str): the lookup key for the entry
            datatype (str): the datatype metadata for the entry
            title (str): the title of the entry
            description (str): the description of the entry
            default (Any): the default value to use for the entry
        """
        self.data[key] = {
            "datatype": datatype,
            "title": title,
            "description": description,
            "default": default,
            "value": default,
        }


class TechSupportBot(commands.Bot):
    """The main bot object."""

    CONFIG_RECEIVE_WARNING_TIME_MS: int = 1000
    DM_GUILD_ID: str = "dmcontext"
    CONFIG_PATH = "./config.yml"
    EXTENSIONS_DIR_NAME = "commands"
    EXTENSIONS_DIR = f"{os.path.join(os.path.dirname(__file__))}/{EXTENSIONS_DIR_NAME}"
    FUNCTIONS_DIR_NAME = "functions"
    FUNCTIONS_DIR = f"{os.path.join(os.path.dirname(__file__))}/{FUNCTIONS_DIR_NAME}"
    ExtensionConfig = ExtensionConfig

    def __init__(self, intents=None, allowed_mentions=None):
        self._startup_time = None

        self.owner: discord.User = None
        self.__startup_time: datetime = None
        self.guild_config_lock = None
        self.guild_configs: dict[str, munch.Munch] = {}
        self.db = None
        self.extension_configs = munch.DefaultMunch(None)
        self.extension_states = munch.DefaultMunch(None)
        self.file_config = None
        self.load_file_config()

        # Call the discord.py init function to create a new commands.Bot object
        super().__init__(
            command_prefix=self.get_prefix,
            intents=intents,
            allowed_mentions=allowed_mentions,
        )

        if self.file_config.logging.queue_enabled:
            self.logger = botlogging.DelayedLogger(
                discord_bot=self,
                name=self.__class__.__name__,
                send=not self.file_config.logging.block_discord_send,
                wait_time=self.file_config.logging.queue_wait_seconds,
            )

        else:
            self.logger = botlogging.BotLogger(
                discord_bot=self,
                name=self.__class__.__name__,
                send=not self.file_config.logging.block_discord_send,
            )

        self.command_rate_limit_bans: expiringdict.ExpiringDict[
            str, bool
        ] = expiringdict.ExpiringDict(
            max_len=5000,
            max_age_seconds=600,
        )
        self.command_execute_history: dict[str, dict[int, bool]] = {}
        self.http_functions = http.HTTPCalls(self)

        # Set the app command on error function to log errors in slash commands
        self.tree.on_error = self.on_app_command_error

    # Entry point

    async def start(self):
        """Starts the event loop and blocks until interrupted."""

        if isinstance(self.logger, botlogging.DelayedLogger):
            self.logger.register_queue()
            asyncio.create_task(self.logger.run())

        # Start the IRC bot in an asynchronous task
        irc_config = getattr(self.file_config.api, "irc")
        if irc_config.enable_irc:
            await self.logger.send_log(
                message="Connecting to IRC...", level=LogLevel.DEBUG, console_only=True
            )
            # Make the IRC class in such a way to allow reload without desctruction
            # We need to pass it the running loop so it can interact with discord
            await self.start_irc()

        # this is required for the bot
        await self.logger.send_log(
            message="Connecting to Postgres...", level=LogLevel.DEBUG, console_only=True
        )
        self.db = await self.get_postgres_ref()

        await self.logger.send_log(
            message="Logging into Discord...", level=LogLevel.DEBUG, console_only=True
        )
        self.guild_config_lock = asyncio.Lock()
        await super().start(self.file_config.bot_config.auth_token)

    # Discord.py called functions

    async def setup_hook(self):
        """This function is automatically called after the bot has been logged into discord
        This loads postgres, extensions, and the help menu
        """
        await self.logger.send_log(
            message="Loading extensions...", level=LogLevel.DEBUG, console_only=True
        )
        self.remove_command("help")
        self.extension_name_list = []
        await self.load_extensions()

        if self.db:
            await self.logger.send_log(
                message="Syncing Postgres tables...",
                level=LogLevel.DEBUG,
                console_only=True,
            )
            self.models = munch.DefaultMunch(None)
            databases.setup_models(self)
            await self.db.gino.create_all()

        # Load all guild config objects into self.guild_configs object
        all_config = await self.models.Config.query.gino.all()
        for config in all_config:
            self.guild_configs[config.guild_id] = munch.munchify(
                json.loads(config.config)
            )

        # Ensure all guilds have a config
        for guild in self.guilds:
            await self.register_new_guild_config(str(guild.id))

        await self.logger.send_log(
            message="Loading Help commands...", level=LogLevel.DEBUG, console_only=True
        )

    async def cleanup(self):
        """Cleans up after the event loop is interupted."""
        await self.logger.send_log(
            message="Cleaning up...", level=LogLevel.DEBUG, console_only=True
        )
        await super().close()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Configures a new guild upon joining.

        parameters:
            guild (discord.Guild): the guild that was joined
        """
        self.register_new_guild_config(str(guild.id))
        for cog in self.cogs.values():
            if getattr(cog, "COG_TYPE", "").lower() == "loop":
                try:
                    await cog.register_new_tasks(guild)
                except Exception as exception:
                    await self.logger.send_log(
                        message="Could not register loop tasks for cog on guild join",
                        level=LogLevel.ERROR,
                        context=LogContext(guild=guild),
                        exception=exception,
                    )

        await super().on_guild_join(guild)

    async def can_run(self, ctx: commands.Context, *, call_once=False) -> bool:
        """Wraps the default can_run check to evaluate bot-admin permission.

        parameters:
            ctx (commands.Context): the context associated with the command
            call_once (bool): True if the check should be retrieved from the call_once attribute
        """
        await self.logger.send_log(
            message="Checking if command can run",
            level=LogLevel.DEBUG,
            context=LogContext(guild=ctx.guild, channel=ctx.channel),
            console_only=True,
        )
        is_bot_admin = await self.is_bot_admin(ctx)
        config = self.guild_configs[str(ctx.guild.id)]

        # Rate limiter
        if config.rate_limit.get("enabled", False):
            identifier = f"{ctx.author.id}-{ctx.guild.id}"

            if identifier not in self.command_execute_history:
                self.command_execute_history[identifier] = expiringdict.ExpiringDict(
                    max_len=20,
                    max_age_seconds=config.rate_limit.time,
                )

            if ctx.message.id not in self.command_execute_history[identifier]:
                self.command_execute_history[identifier][ctx.message.id] = True

            if (
                len(self.command_execute_history[identifier])
                > config.rate_limit.commands
            ):
                self.command_rate_limit_bans[identifier] = True

            if (
                identifier in self.command_rate_limit_bans
                and not ctx.author.guild_permissions.administrator
            ):
                raise custom_errors.CommandRateLimit

        extension_name = self.get_command_extension_name(ctx.command)
        if extension_name:
            config = self.guild_configs[str(ctx.guild.id)]
            if (
                not extension_name in config.enabled_extensions
                and extension_name != "config"
            ):
                raise custom_errors.ExtensionDisabled

        cog = getattr(ctx.command, "cog", None)
        if getattr(cog, "ADMIN_ONLY", False) and not is_bot_admin:
            # treat this as a command error to be caught by the dispatcher
            raise commands.MissingPermissions(["bot_admin"])

        if is_bot_admin:
            result = True
        else:
            result = await super().can_run(ctx, call_once=call_once)

        return result

    async def on_ready(self) -> None:
        """Callback for when the bot is finished starting up."""
        self.__startup_time = datetime.datetime.utcnow()
        await self.logger.send_log(
            message="Bot online", level=LogLevel.INFO, console_only=True
        )
        await self.get_owner()

    async def on_message(self, message: discord.Message) -> None:
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
            attachment_urls = ", ".join(a.url for a in message.attachments)
            content_string = f'"{message.content}"' if message.content else ""
            attachment_string = f"({attachment_urls})" if attachment_urls else ""
            await self.logger.send_log(
                message=(
                    f"PM from `{message.author}`: {content_string} {attachment_string}"
                ),
                level=LogLevel.INFO,
            )

        await self.process_commands(message)

    # Guild config management functions

    async def register_new_guild_config(self, guild: str) -> bool:
        """This creates a config for a new guild if needed

        Args:
            guild (str): The id of the guild to create config for, in string form

        Returns:
            bool: True if a config was created, False if a config already existed
        """
        async with self.guild_config_lock:
            try:
                config = self.guild_configs[guild]
            except KeyError:
                config = None
            if not config:
                await self.create_new_context_config(guild)
                return True
            return False

    async def create_new_context_config(self, lookup: str) -> munch.Munch:
        """Creates a new guild config based on a lookup key (usually a guild ID).

        parameters:
            lookup (str): the primary key for the guild config document object
        """
        extensions_config = munch.DefaultMunch(None)

        for extension_name, extension_config in self.extension_configs.items():
            if extension_config:
                # don't attach to guild config if extension isn't configurable
                extensions_config[extension_name] = extension_config.data
        self.extension_name_list.sort()

        config_ = munch.DefaultMunch(None)

        config_.guild_id = str(lookup)
        config_.command_prefix = self.file_config.bot_config.default_prefix
        config_.logging_channel = None
        config_.member_events_channel = None
        config_.guild_events_channel = None
        config_.private_channels = []
        config_.enabled_extensions = self.extension_name_list
        config_.nickname_filter = False
        config_.enable_logging = True
        config_.rate_limit = munch.DefaultMunch(None)
        config_.rate_limit.enabled = False
        config_.rate_limit.commands = 4
        config_.rate_limit.time = 10

        config_.extensions = extensions_config

        try:
            await self.logger.send_log(
                message=f"Inserting new config for lookup key: {lookup}",
                level=LogLevel.DEBUG,
                context=LogContext(guild=self.get_guild(lookup)),
                console_only=True,
            )
            # Modify the database
            await self.write_new_config(str(lookup), json.dumps(config_))

            # Modify the local cache
            self.guild_configs[lookup] = config_

        except Exception as exception:
            # safely finish because the new config is still useful
            await self.logger.send_log(
                message="Could not insert guild config into Postgres",
                level=LogLevel.ERROR,
                context=LogContext(guild=self.get_guild(lookup)),
                exception=exception,
            )

        return config_

    async def write_new_config(self, guild_id: str, config: str) -> None:
        """Takes a config and guild and updates the config in the database
        This is rarely needed

        Args:
            guild_id (str): The str ID of the guild the config belongs to
            config (str): The str representation of the json config
        """
        database_config = await self.models.Config.query.where(
            self.models.Config.guild_id == guild_id
        ).gino.first()
        if database_config:
            await database_config.update(config=str(config)).apply()
        else:
            new_database_config = self.models.Config(
                guild_id=str(guild_id),
                config=str(config),
            )
            await new_database_config.create()

    def add_extension_config(self, extension_name, config):
        """Adds a base config object for a given extension.

        parameters:
            extension_name (str): the name of the extension
            config (ExtensionConfig): the extension config object
        """
        if not isinstance(config, self.ExtensionConfig):
            raise ValueError("config must be of type ExtensionConfig")
        self.extension_configs[extension_name] = config

    async def get_log_channel_from_guild(
        self, guild: discord.Guild, key: str
    ) -> str | None:
        """Gets the log channel ID associated with the given guild.

        This also checks if the channel exists in the correct guild.

        parameters:
            guild (discord.Guild): the guild object to reference
            key (string): the key to use when looking up the channel
        """
        if not guild:
            return None

        config = self.guild_configs[str(guild.id)]
        channel_id = config.get(key)

        if not channel_id:
            return None

        if not guild.get_channel(int(channel_id)):
            return None

        return channel_id

    # File config loading functions

    def load_file_config(self, validate=True):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH, encoding="utf8") as iostream:
            config_ = yaml.safe_load(iostream)

        self.file_config = munch.munchify(config_)

        self.file_config.bot_config.disabled_extensions = (
            self.file_config.bot_config.disabled_extensions or []
        )

        if not validate:
            return

        for subsection in ["required"]:
            self.validate_bot_config_subsection("bot_config", subsection)

    def validate_bot_config_subsection(self, section, subsection):
        """Loops through a config subsection to check for missing values.

        parameters:
            section (str): the section name containing the subsection
            subsection (str): the subsection name
        """
        for key, value in self.file_config.get(section, {}).get(subsection, {}).items():
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

    # Error handling and logging functions

    async def on_app_command_error(
        self,
        interaction: discord.Interaction[discord.Client],
        error: app_commands.AppCommandError,
    ) -> None:
        """Error handler for the slowmode extension."""
        error_message = await self.handle_error(
            exception=error, channel=interaction.channel, guild=interaction.guild
        )

        if not error_message:
            return

        embed = auxiliary.prepare_deny_embed(message=error_message)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

    async def handle_error(
        self,
        exception: Exception,
        channel: discord.abc.Messageable,
        guild: discord.Guild,
    ) -> str:
        """Handles the formatting and logging of command and app command errors

        Args:
            exception (Exception): The exception object generated
            channel (discord.abc.Messageable): The channel the command was run in
            guild (discord.Guild): The guild the command was run in

        Returns:
            str: The pretty string format that should be shared with the user
        """
        # Get the custom error response we made for the error
        message_template = custom_errors.COMMAND_ERROR_RESPONSES.get(
            exception.__class__, ""
        )
        # see if we have mapped this error to no response (None)
        # or if we have added it to the global ignore list of errors
        if (
            message_template is None
            or exception.__class__ in custom_errors.IGNORED_ERRORS
        ):
            return
        # otherwise set it a default error message
        if message_template == "":
            message_template = custom_errors.ErrorResponse()

        error_message = message_template.get_message(exception)

        log_channel = await self.get_log_channel_from_guild(
            guild=guild, key="logging_channel"
        )

        # Ensure that error messages aren't too long.
        # This ONLY changes the user facing error, the stack trace isn't impacted
        if len(error_message) > 1000:
            error_message = error_message[:1000]
            error_message += "..."

        # Only log stack trace if you should
        if not getattr(exception, "dont_print_trace", False):
            await self.logger.send_log(
                message=f"Command error: {exception}",
                level=LogLevel.ERROR,
                channel=log_channel,
                context=LogContext(guild=guild, channel=channel),
                exception=exception,
            )

        # Return the string error message and allow the context/interaction to respond properly
        return error_message

    async def on_command_error(
        self, context: commands.Context, exception: Exception
    ) -> None:
        """Catches command errors and sends them to the error logger for processing.

        parameters:
            context (commands.Context): the context associated with the exception
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

        error_message = await self.handle_error(
            exception=exception, channel=context.channel, guild=context.guild
        )
        if not error_message:
            return

        await auxiliary.send_deny_embed(message=error_message, channel=context.channel)

    # Postgres setup functions

    def generate_db_url(self):
        """Dynamically converts config to a Postgres url."""
        db_type = "postgres"

        try:
            config_child = getattr(self.file_config.database, db_type)

            user = config_child.user
            password = config_child.password

            name = getattr(config_child, "name")

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
        await self.logger.send_log(
            message="Obtaining and binding to Gino instance",
            level=LogLevel.DEBUG,
            console_only=True,
        )

        db_ref = gino.Gino()
        db_url = self.generate_db_url()
        await db_ref.set_bind(db_url)

        db_ref.Model.__table_args__ = {"extend_existing": True}

        return db_ref

    # Extension loading and management functions

    async def get_potential_extensions(self):
        """Gets the current list of extensions in the defined directory.
        This ONLY gets commands, not functions"""
        self.logger.console.info(f"Searching {self.EXTENSIONS_DIR} for extensions")
        extensions_list = [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.EXTENSIONS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]
        return extensions_list

    async def get_potential_function_extensions(self):
        """Gets the current list of extensions in the defined directory.
        This ONLY gets functions, not commands"""
        self.logger.console.info(f"Searching {self.FUNCTIONS_DIR} for extensions")
        extensions_list = [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.FUNCTIONS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]
        return extensions_list

    async def load_extensions(self, graceful=True):
        """Loads all extensions currently in the extensions directory.

        parameters:
            graceful (bool): True if extensions should gracefully fail to load
        """
        self.logger.console.debug("Retrieving commands")
        for extension_name in await self.get_potential_extensions():
            if extension_name in self.file_config.bot_config.disabled_extensions:
                self.logger.console.debug(
                    f"{extension_name} is disabled on startup - ignoring load"
                )
                continue

            try:
                await self.load_extension(
                    f"{self.EXTENSIONS_DIR_NAME}.{extension_name}"
                )
                self.extension_name_list.append(extension_name)
            except Exception as exception:
                self.logger.console.error(
                    f"Failed to load extension {extension_name}: {exception}"
                )
                if not graceful:
                    raise exception

        self.logger.console.debug("Retrieving functions")
        for extension_name in await self.get_potential_function_extensions():
            if extension_name in self.file_config.bot_config.disabled_extensions:
                self.logger.console.debug(
                    f"{extension_name} is disabled on startup - ignoring load"
                )
                continue

            try:
                await self.load_extension(f"{self.FUNCTIONS_DIR_NAME}.{extension_name}")
                self.extension_name_list.append(extension_name)
            except Exception as exception:
                self.logger.console.error(
                    f"Failed to load extension {extension_name}: {exception}"
                )
                if not graceful:
                    raise exception

    def get_command_extension_name(self, command):
        """Gets the subname of an extension from a command.
        Used only for commands, should never be run for a function

        parameters:
            command (discord.ext.commands.Command): the command to reference
        """
        if not command.module.startswith(f"{self.EXTENSIONS_DIR_NAME}."):
            return None
        extension_name = command.module.split(".")[1]
        return extension_name

    async def register_file_extension(self, extension_name, fp):
        """Offers an interface for loading an extension from an external source.

        This saves the external file data to the OS, without any validation.

        parameters:
            extension_name (str): the name of the extension to register
            fp (io.BufferedIOBase): the file-like object to save to disk
        """
        if not extension_name:
            raise NameError("Invalid extension name")

        try:
            await self.unload_extension(f"{self.EXTENSIONS_DIR_NAME}.{extension_name}")
        except commands.errors.ExtensionNotLoaded:
            pass

        with open(f"{self.EXTENSIONS_DIR}/{extension_name}.py", "wb") as file_handle:
            file_handle.write(fp)

    # Bot properties

    async def is_bot_admin(self, ctx: commands.Context) -> bool:
        """Processes command context against admin/owner data.

        Command checks are disabled if the context author is the owner.

        They are also ignored if the author is bot admin in the config.

        parameters:
            ctx (discord.ext.Context): the context associated with the command
        """
        await self.logger.send_log(
            message="Checking context against bot admins",
            level=LogLevel.DEBUG,
            context=LogContext(guild=ctx.guild, channel=ctx.channel),
            console_only=True,
        )

        owner = await self.get_owner()
        if getattr(owner, "id", None) == ctx.author.id:
            return True

        if ctx.message.author.id in [
            int(id) for id in self.file_config.bot_config.admins.ids
        ]:
            return True

        role_is_admin = False
        for role in getattr(ctx.message.author, "roles", []):
            if role.name in self.file_config.bot_config.admins.roles:
                role_is_admin = True
                break
        if role_is_admin:
            return True

        return False

    async def get_owner(self) -> discord.User:
        """Gets the owner object from the bot application."""
        if not self.owner:
            try:
                # If this isn't console only, it is a forever recursion
                await self.logger.send_log(
                    message="Looking up bot owner",
                    level=LogLevel.DEBUG,
                    console_only=True,
                )
                app_info = await self.application_info()
                self.owner = app_info.owner
            except discord.errors.HTTPException:
                self.owner = None

        return self.owner

    @property
    def startup_time(self) -> datetime:
        """Gets the startup timestamp of the bot."""
        return self.__startup_time

    async def get_prefix(self, message: discord.Message) -> str:
        """Gets the appropriate prefix for a command.

        parameters:
            message (discord.Message): the message to check against
        """
        guild_config = self.guild_configs[str(message.guild.id)]
        return getattr(
            guild_config, "command_prefix", self.file_config.bot_config.default_prefix
        )

    # Other stuff

    async def slash_command_log(self, interaction: discord.Interaction) -> None:
        """A command to log the call of a slash command

        Args:
            interaction (discord.Interaction): The interaction the slash command generated
        """
        embed = discord.Embed()
        embed.add_field(name="User", value=interaction.user)
        embed.add_field(
            name="Channel", value=getattr(interaction.channel, "name", "DM")
        )
        embed.add_field(name="Server", value=getattr(interaction.guild, "name", "None"))
        embed.add_field(name="Namespace", value=f"{interaction.namespace}")

        log_channel = await self.get_log_channel_from_guild(
            interaction.guild, key="logging_channel"
        )

        sliced_content = interaction.command.qualified_name[:100]
        message = f"Command detected: `/{sliced_content}`"

        await self.logger.send_log(
            message=message,
            level=LogLevel.INFO,
            context=LogContext(guild=interaction.guild, channel=interaction.channel),
            channel=log_channel,
            embed=embed,
        )

    async def start_irc(self):
        """Starts the IRC connection in a seperate thread

        Args:
            irc (irc.IRC): The IRC object to start the socket on

        Returns:
            bool: True if the connection was successful, False if it was not
        """
        irc_config = getattr(self.file_config.api, "irc")
        loop = asyncio.get_running_loop()

        irc_bot = ircrelay.IRCBot(
            loop=loop,
            server=irc_config.server,
            port=irc_config.port,
            channels=irc_config.channels,
            username=irc_config.name,
            password=irc_config.password,
        )
        self.irc = irc_bot

        irc_thread = threading.Thread(target=irc_bot.start)
        await self.logger.send_log(
            message="Logging in to IRC", level=LogLevel.INFO, console_only=True
        )
        irc_thread.start()
