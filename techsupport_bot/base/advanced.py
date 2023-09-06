"""Module for defining the advanced bot methods."""
import asyncio
import datetime
import random
import re
import string
import time

import discord
import error
import expiringdict
import munch
from base import auxiliary, data
from botlogging import LogContext, LogLevel
from discord.ext import commands
from unidecode import unidecode


class AdvancedBot(data.DataBot):
    """
    Advanced extension bot with most base features,
    including per-guild config and event logging.
    """

    GUILD_CONFIG_COLLECTION = "guild_config"
    CONFIG_RECEIVE_WARNING_TIME_MS = 1000
    DM_GUILD_ID = "dmcontext"

    def __init__(self, *args, **kwargs):
        self.owner = None
        self.__startup_time = None
        self.guild_config_collection = None
        self.guild_config_lock = None
        super().__init__(*args, prefix=self.get_prefix, **kwargs)
        self.guild_config_cache = expiringdict.ExpiringDict(
            max_len=self.file_config.cache.guild_config_cache_length,
            max_age_seconds=self.file_config.cache.guild_config_cache_seconds,
        )

    async def start(self, *args, **kwargs):
        """Function is automatically called when the bot is started by discord.py"""
        self.guild_config_lock = asyncio.Lock()
        await super().start(*args, **kwargs)

    async def get_prefix(self, message):
        """Gets the appropriate prefix for a command.

        parameters:
            message (discord.Message): the message to check against
        """
        guild_config = await self.get_context_config(guild=message.guild)
        return getattr(
            guild_config, "command_prefix", self.file_config.bot_config.default_prefix
        )

    async def get_all_context_configs(self, projection, limit=100):
        """Gets all context configs.

        parameters:
            projection (dict): the MongoDB projection for returned data
            limit (int): the max number of config objects to return
        """
        configs = []
        cursor = self.guild_config_collection.find({}, projection)
        for document in await cursor.to_list(length=limit):
            configs.append(munch.DefaultMunch.fromDict(document, None))
        return configs

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
        start = time.time()

        if ctx:
            guild_from_ctx = getattr(ctx, "guild", None)
            lookup = guild_from_ctx.id if guild_from_ctx else self.DM_GUILD_ID
        elif guild:
            lookup = guild.id
        else:
            return None

        lookup = str(lookup)

        config_ = None

        if get_from_cache:
            config_ = self.guild_config_cache.get(lookup)

        if not config_:
            # locking prevents duplicate configs being made
            async with self.guild_config_lock:
                config_ = await self.guild_config_collection.find_one(
                    {"guild_id": {"$eq": lookup}}
                )

                if not config_:
                    await self.logger.send_log(
                        message="No config found in MongoDB",
                        level=LogLevel.DEBUG,
                        console_only=True,
                    )
                    if create_if_none:
                        config_ = await self.create_new_context_config(lookup)
                else:
                    config_ = await self.sync_config(config_)

                if config_:
                    self.guild_config_cache[lookup] = config_

        time_taken = (time.time() - start) * 1000.0

        if time_taken > self.CONFIG_RECEIVE_WARNING_TIME_MS:
            await self.logger.send_log(
                message=(
                    f"Context config receive time = {time_taken} ms (over"
                    f" {self.CONFIG_RECEIVE_WARNING_TIME_MS} threshold)"
                ),
                level=LogLevel.WARNING,
                context=LogContext(guild=self.get_guild(lookup)),
            )

        return config_

    async def create_new_context_config(self, lookup: str):
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

        config_.extensions = extensions_config

        try:
            await self.logger.send_log(
                message=f"Inserting new config for lookup key: {lookup}",
                level=LogLevel.DEBUG,
                context=LogContext(guild=self.get_guild(lookup)),
                console_only=True,
            )
            await self.guild_config_collection.insert_one(config_)
        except Exception as exception:
            # safely finish because the new config is still useful
            await self.logger.send_log(
                message="Could not insert guild config into MongoDB",
                level=LogLevel.ERROR,
                context=LogContext(guild=self.get_guild(lookup)),
                exception=exception,
            )

        return config_

    async def sync_config(self, config_object):
        """Syncs the given config with the currently loaded extensions.

        parameters:
            config_object (dict): the guild config object
        """
        config_object = munch.munchify(config_object)

        should_update = False

        for (
            extension_name,
            extension_config_from_data,
        ) in self.extension_configs.items():
            extension_config = config_object.extensions.get(extension_name)
            if not extension_config and extension_config_from_data:
                should_update = True
                await self.logger.send_log(
                    message=(
                        f"Found extension {extension_name} not in config with ID"
                        f" {config_object.guild_id}"
                    ),
                    level=LogLevel.DEBUG,
                    context=LogContext(guild=self.get_guild(config_object.guild_id)),
                    console_only=True,
                )
                config_object.extensions[
                    extension_name
                ] = extension_config_from_data.data

        if should_update:
            await self.logger.send_log(
                message=(
                    f"Updating guild config for lookup key: {config_object.guild_id}"
                ),
                level=LogLevel.DEBUG,
                context=LogContext(guild=self.get_guild(config_object.guild_id)),
                console_only=True,
            )
            await self.guild_config_collection.replace_one(
                {"_id": config_object.get("_id")}, config_object
            )

        return config_object

    async def can_run(self, ctx, *, call_once=False):
        """Wraps the default can_run check to evaluate bot-admin permission.

        parameters:
            ctx (discord.ext.Context): the context associated with the command
            call_once (bool): True if the check should be retrieved from the call_once attribute
        """
        await self.logger.send_log(
            message="Checking if command can run",
            level=LogLevel.DEBUG,
            context=LogContext(guild=ctx.guild, channel=ctx.channel),
            console_only=True,
        )

        extension_name = self.get_command_extension_name(ctx.command)
        if extension_name:
            config = await self.get_context_config(ctx)
            if not extension_name in config.enabled_extensions:
                raise error.ExtensionDisabled

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

    async def get_owner(self):
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
    def startup_time(self):
        """Gets the startup timestamp of the bot."""
        return self.__startup_time

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

    async def slash_command_log(self, interaction):
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

    async def on_ready(self):
        """Callback for when the bot is finished starting up."""
        self.__startup_time = datetime.datetime.utcnow()
        await self.logger.send_log(
            message="Bot online", level=LogLevel.INFO, console_only=True
        )
        await self.get_owner()

    def format_username(self, username: str) -> str:
        """Formats a username to be all ascii and easily readable and pingable

        Args:
            username (str): The original users username

        Returns:
            str: The new username with all formatting applied
        """

        # Prepare a random string, just in case
        random_string = "".join(random.choice(string.ascii_letters) for _ in range(10))

        # Step 1 - Force all ascii
        username = unidecode(username)

        # Step 2 - Remove all markdown
        markdown_pattern = r"(\*\*|__|\*|_|\~\~|`|#+|-{3,}|\|{3,}|>)"
        username = re.sub(markdown_pattern, "", username)

        # Step 3 - Strip
        username = username.strip()

        # Step 4 - Fix dumb spaces
        username = re.sub(r"\s+", " ", username)
        username = re.sub(r"(\b\w) ", r"\1", username)

        # Step 5 - Start with letter
        match = re.search(r"[A-Za-z]", username)
        if match:
            username = username[match.start() :]
        else:
            username = ""

        # Step 6 - Length check
        if len(username) < 3 and len(username) > 0:
            username = f"{username}-USER-{random_string}"
        elif len(username) == 0:
            username = f"USER-{random_string}"
        username = username[:32]

        return username

    async def on_member_join(self, member: discord.Member):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join"""
        config = await self.get_context_config(guild=member.guild)

        if config.get("nickname_filter", False):
            temp_name = self.format_username(member.display_name)
            if temp_name != member.display_name:
                await member.edit(nick=temp_name)
                try:
                    await member.send(
                        "Your nickname has been changed to make it easy to read and"
                        f" ping your name. Your new nickname is {temp_name}."
                    )
                except discord.Forbidden:
                    channel = config.get("logging_channel")
                    await self.logger.send_log(
                        message=f"Could not DM {member.name} about nickname changes",
                        level=LogLevel.WARNING,
                        channel=channel,
                        context=LogContext(guild=member.guild),
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

        message_template = error.COMMAND_ERROR_RESPONSES.get(exception.__class__, "")
        # see if we have mapped this error to no response (None)
        # or if we have added it to the global ignore list of errors
        if message_template is None or exception.__class__ in error.IGNORED_ERRORS:
            return
        # otherwise set it a default error message
        if message_template == "":
            message_template = error.ErrorResponse()

        error_message = message_template.get_message(exception)

        log_channel = await self.get_log_channel_from_guild(
            getattr(context, "guild", None), key="logging_channel"
        )

        # 1000 character cap
        if len(error_message) < 1000:
            await auxiliary.send_deny_embed(
                message=error_message, channel=context.channel
            )
        else:
            await auxiliary.send_deny_embed(
                message=(
                    "Command raised an error and the error message too long to send!"
                )
                + f" First 1000 chars:\n{error_message[:1000]}",
                channel=context.channel,
            )

        # Stops execution if dont_print_trace is True
        if hasattr(exception, "dont_print_trace") and exception.dont_print_trace:
            return

        await self.logger.send_log(
            message=f"Command error: {exception}",
            level=LogLevel.ERROR,
            channel=log_channel,
            context=LogContext(guild=context.guild, channel=context.channel),
            exception=exception,
        )

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
            attachment_urls = ", ".join(a.url for a in message.attachments)
            content_string = f'"{message.content}"' if message.content else ""
            attachment_string = f"({attachment_urls})" if attachment_urls else ""
            await self.bot.logger.send_log(
                message=(
                    f"PM from `{message.author}`: {content_string} {attachment_string}"
                ),
                level=LogLevel.INFO,
            )

        await self.process_commands(message)
