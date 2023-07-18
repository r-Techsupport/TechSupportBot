"""Module for defining the advanced bot methods."""
import asyncio
import datetime
import sys
import time

import discord
import error
import expiringdict
import munch
import util
from base import auxiliary
from discord.ext import commands

from .data import DataBot


class AdvancedBot(DataBot):
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
            max_len=self.file_config.main.cache.guild_config_cache_length,
            max_age_seconds=self.file_config.main.cache.guild_config_cache_seconds,
        )

    async def start(self, *args, **kwargs):
        self.guild_config_lock = asyncio.Lock()
        await super().start(*args, **kwargs)

    async def get_prefix(self, message):
        """Gets the appropriate prefix for a command.

        parameters:
            message (discord.Message): the message to check against
        """
        guild_config = await self.get_context_config(guild=message.guild)
        return getattr(
            guild_config, "command_prefix", self.file_config.main.default_prefix
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
                    await self.logger.debug("No config found in MongoDB")
                    if create_if_none:
                        config_ = await self.create_new_context_config(lookup)
                else:
                    config_ = await self.sync_config(config_)

                if config_:
                    self.guild_config_cache[lookup] = config_

        time_taken = (time.time() - start) * 1000.0

        if time_taken > self.CONFIG_RECEIVE_WARNING_TIME_MS:
            await self.logger.warning(
                f"Context config receive time = {time_taken} ms \
                (over {self.CONFIG_RECEIVE_WARNING_TIME_MS} threshold)",
                send=True,
            )

        return config_

    async def create_new_context_config(self, lookup):
        """Creates a new guild config based on a lookup key (usually a guild ID).

        parameters:
            lookup (str): the primary key for the guild config document object
        """
        extensions_config = munch.DefaultMunch(None)

        for extension_name, extension_config in self.extension_configs.items():
            if extension_config:
                # don't attach to guild config if extension isn't configurable
                extensions_config[extension_name] = extension_config.data

        config_ = munch.DefaultMunch(None)

        config_.guild_id = str(lookup)
        config_.command_prefix = self.file_config.main.default_prefix
        config_.logging_channel = None
        config_.member_events_channel = None
        config_.guild_events_channel = None
        config_.private_channels = []
        config_.enabled_extensions = []

        config_.extensions = extensions_config

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
                await self.logger.debug(
                    f"Found extension {extension_name} not \
                    in config with ID {config_object.guild_id}"
                )
                config_object.extensions[
                    extension_name
                ] = extension_config_from_data.data

        if should_update:
            await self.logger.debug(
                f"Updating guild config for lookup key: {config_object.guild_id}"
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
        await self.logger.debug("Checking if command can run")

        extension_name = self.get_command_extension_name(ctx.command)
        if extension_name:
            config = await self.get_context_config(ctx)
            if not extension_name in config.enabled_extensions:
                raise error.ExtensionDisabled(
                    "extension is disabled for this server/context"
                )

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

        if ctx.message.author.id in [
            int(id) for id in self.file_config.main.admins.ids
        ]:
            return True

        role_is_admin = False
        for role in getattr(ctx.message.author, "roles", []):
            if role.name in self.file_config.main.admins.roles:
                role_is_admin = True
                break
        if role_is_admin:
            return True

        return False

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

        await self.logger.info(message, embed=embed, send=True, channel=log_channel)

    async def guild_log(self, guild, key, log_type, message, **kwargs):
        """Wrapper for logging directly to a guild's log channel.

        parameters:
            guild (discord.Guild): the guild object to reference
            key (string): the key to use when looking up the channel
            log_type (string): the log type to use (info, error, warning, etc.)
            message (string): the log message
        """
        log_channel = await self.get_log_channel_from_guild(guild, key)
        await getattr(self.logger, log_type)(message, channel=log_channel, **kwargs)

    async def on_ready(self):
        """Callback for when the bot is finished starting up."""
        self.__startup_time = datetime.datetime.utcnow()
        await self.logger.info("Bot online")
        await self.get_owner()

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
            await self.logger.info(
                f"PM from `{message.author}`: {content_string} {attachment_string}",
                send=True,
            )

        await self.process_commands(message)

    async def on_command(self, ctx):
        """
        See: https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.on_command
        """
        config_ = await self.get_context_config(ctx)
        if str(ctx.channel.id) in config_.get("private_channels", []):
            return

        embed = discord.Embed()
        embed.add_field(name="User", value=ctx.author)
        embed.add_field(name="Channel", value=getattr(ctx.channel, "name", "DM"))
        embed.add_field(name="Server", value=getattr(ctx.guild, "name", "None"))

        log_channel = await self.get_log_channel_from_guild(
            ctx.guild, key="logging_channel"
        )

        sliced_content = ctx.message.content[:100]
        message = f"Command detected: {sliced_content}"

        await self.logger.info(
            message, embed=embed, context=ctx, send=True, channel=log_channel
        )

    async def on_error(self, event_method, *_args, **_kwargs):
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
            await self.logger.error(
                f"Command error: {exception}",
                exception=exception,
                channel=log_channel,
            )

        else:
            await auxiliary.send_deny_embed(
                message="Command raised an error and the error message too long to send!"
                + f" First 1000 chars:\n{error_message[:1000]}",
                channel=context.channel,
            )
            await self.logger.error(
                "Command raised an error and the error message too long to send!"
                + " See traceback below",
                exception=exception,
                channel=log_channel,
            )

    async def on_connect(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_connect"""
        await self.logger.info("Connected to Discord")

    async def on_resumed(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_resumed"""
        await self.logger.info("Resume event")

    async def on_disconnect(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_disconnect"""
        await self.logger.info("Disconnected from Discord")

    async def on_message_delete(self, message):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_delete"""
        guild = getattr(message.channel, "guild", None)
        channel_id = getattr(message.channel, "id", None)

        # Ignore ephemeral slash command messages
        if not guild and message.type == discord.MessageType.chat_input_command:
            return

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        embed = discord.Embed()
        embed.add_field(name="Content", value=message.content[:1024] or "None")
        if len(message.content) > 1024:
            embed.add_field(name="\a", value=message.content[1025:2048])
        if len(message.content) > 2048:
            embed.add_field(name="\a", value=message.content[2049:3072])
        if len(message.content) > 3072:
            embed.add_field(name="\a", value=message.content[3073:4096])
        embed.add_field(name="Author", value=message.author)
        embed.add_field(
            name="Channel",
            value=getattr(message.channel, "name", "DM"),
        )
        embed.add_field(name="Server", value=getattr(guild, "name", "None"))
        embed.set_footer(text=f"Author ID: {message.author.id}")

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Message with ID {message.id} deleted",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_bulk_message_delete(self, messages):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_bulk_message_delete
        """
        guild = getattr(messages[0].channel, "guild", None)
        channel_id = getattr(messages[0].channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        unique_channels = set()
        unique_servers = set()
        for message in messages:
            unique_channels.add(message.channel.name)
            unique_servers.add(
                f"{message.channel.guild.name} ({message.channel.guild.id})"
            )

        embed = discord.Embed()
        embed.add_field(name="Channels", value=",".join(unique_channels))
        embed.add_field(name="Servers", value=",".join(unique_servers))

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            message=f"{len(messages)} messages bulk deleted!",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_message_edit(self, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_edit"""
        # this seems to spam, not sure why
        if before.content == after.content:
            return

        guild = getattr(before.channel, "guild", None)
        channel_id = getattr(before.channel, "id", None)

        # Ignore ephemeral slash command messages
        if not guild and before.type == discord.MessageType.chat_input_command:
            return

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        attrs = ["content", "embeds"]
        diff = util.get_object_diff(before, after, attrs)
        embed = discord.Embed()
        embed = util.add_diff_fields(embed, diff)
        embed.add_field(name="Author", value=before.author)
        embed.add_field(name="Channel", value=getattr(before.channel, "name", "DM"))
        embed.add_field(
            name="Server",
            value=guild,
        )
        embed.set_footer(text=f"Author ID: {before.author.id}")

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Message edit detected on message with ID {before.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_reaction_add(self, reaction, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_add"""
        guild = getattr(reaction.message.channel, "guild", None)
        channel_id = getattr(reaction.message.channel, "id", None)

        if isinstance(reaction.message.channel, discord.DMChannel):
            await self.logger.info(
                f"PM from `{user}`: added {reaction.emoji} reaction \
                    to message {reaction.message.content} in DMs",
                send=True,
            )
            return

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        embed = discord.Embed()
        embed.add_field(name="Emoji", value=reaction.emoji)
        embed.add_field(name="User", value=user)
        embed.add_field(name="Message", value=reaction.message.content or "None")
        embed.add_field(name="Message Author", value=reaction.message.author)
        embed.add_field(
            name="Channel", value=getattr(reaction.message.channel, "name", "DM")
        )
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Reaction added to message with ID {reaction.message.id} by user with ID {user.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_reaction_remove(self, reaction, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_remove"""
        guild = getattr(reaction.message.channel, "guild", None)
        channel_id = getattr(reaction.message.channel, "id", None)

        if isinstance(reaction.message.channel, discord.DMChannel):
            await self.logger.info(
                f"PM from `{user}`: removed {reaction.emoji} reaction \
                    to message {reaction.message.content} in DMs",
                send=True,
            )
            return

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        embed = discord.Embed()
        embed.add_field(name="Emoji", value=reaction.emoji)
        embed.add_field(name="User", value=user)
        embed.add_field(name="Message", value=reaction.message.content or "None")
        embed.add_field(name="Message Author", value=reaction.message.author)
        embed.add_field(
            name="Channel", value=getattr(reaction.message.channel, "name", "DM")
        )
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Reaction removed from message with ID {reaction.message.id} \
            by user with ID {user.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_reaction_clear(self, message, reactions):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_clear
        """
        guild = getattr(message.channel, "guild", None)
        channel_id = getattr(message.channel, "id", None)

        config_ = await self.get_context_config(guild=guild)
        if str(channel_id) in config_.get("private_channels", []):
            return

        unique_emojis = set()
        for reaction in reactions:
            unique_emojis.add(reaction.emoji)

        embed = discord.Embed()
        embed.add_field(name="Emojis", value=",".join(unique_emojis))
        embed.add_field(name="Message", value=message.content or "None")
        embed.add_field(name="Message Author", value=message.author)
        embed.add_field(name="Channel", value=getattr(message.channel, "name", "DM"))
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"{len(reactions)} cleared from message with ID {message.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_channel_delete(self, channel):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_delete
        """
        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild.name)

        log_channel = await self.get_log_channel_from_guild(
            channel.guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Channel with ID {channel.id} deleted in guild with ID {channel.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_channel_create(self, channel):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_create
        """
        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild.name)
        log_channel = await self.get_log_channel_from_guild(
            getattr(channel, "guild", None), key="guild_events_channel"
        )
        await self.logger.info(
            f"Channel with ID {channel.id} created in guild with ID {channel.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_channel_update(self, before, after):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_update
        """
        config_ = await self.get_context_config(guild=before.guild)
        if str(before.id) in config_.get("private_channels", []):
            return

        attrs = [
            "category",
            "changed_roles",
            "name",
            "overwrites",
            "permissions_synced",
            "position",
        ]
        diff = util.get_object_diff(before, after, attrs)

        embed = discord.Embed()
        embed = util.add_diff_fields(embed, diff)
        embed.add_field(name="Channel Name", value=before.name)
        embed.add_field(name="Server", value=before.guild.name)

        log_channel = await self.get_log_channel_from_guild(
            before.guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Channel with ID {before.id} modified in guild with ID {before.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_channel_pins_update(self, channel, _last_pin):
        """
        See:
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_pins_update
        """
        config_ = await self.get_context_config(guild=channel.guild)
        if str(channel.id) in config_.get("private_channels", []):
            return

        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild)

        log_channel = await self.get_log_channel_from_guild(
            channel.guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Channel pins updated in channel with ID {channel.id} \
            in guild with ID {channel.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_integrations_update(self, guild):
        """
        See:
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_integrations_update
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild)
        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Integrations updated in guild with ID {guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_webhooks_update(self, channel):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_webhooks_update"""
        config_ = await self.get_context_config(guild=channel.guild)
        if str(channel.id) in config_.get("private_channels", []):
            return

        embed = discord.Embed()
        embed.add_field(name="Channel", value=channel.name)
        embed.add_field(name="Server", value=channel.guild)

        log_channel = await self.get_log_channel_from_guild(
            channel.guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Webooks updated for channel with ID {channel.id} in guild with ID {channel.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_member_join(self, member):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join"""
        embed = discord.Embed()
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Server", value=member.guild.name)
        log_channel = await self.get_log_channel_from_guild(
            getattr(member, "guild", None), key="member_events_channel"
        )
        await self.logger.info(
            f"Member with ID {member.id} has joined guild with ID {member.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_member_update(self, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_update"""
        changed_role = set(before.roles) ^ set(after.roles)
        if changed_role:
            if len(before.roles) < len(after.roles):
                embed = discord.Embed()
                embed.add_field(name="Roles added", value=next(iter(changed_role)))
                embed.add_field(name="Server", value=before.guild.name)
            else:
                embed = discord.Embed()
                embed.add_field(name="Roles lost", value=next(iter(changed_role)))
                embed.add_field(name="Server", value=before.guild.name)

            log_channel = await self.get_log_channel_from_guild(
                getattr(before, "guild", None), key="member_events_channel"
            )

            await self.logger.info(
                f"Member with ID {before.id} has changed status in guild with ID {before.guild.id}",
                embed=embed,
                send=True,
                channel=log_channel,
            )

    async def on_member_remove(self, member):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_remove"""
        embed = discord.Embed()
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Server", value=member.guild.name)
        log_channel = await self.get_log_channel_from_guild(
            getattr(member, "guild", None), key="member_events_channel"
        )
        await self.logger.info(
            f"Member with ID {member.id} has left guild with ID {member.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_remove(self, guild):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_remove"""
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild.name)
        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Left guild with ID {guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_join(self, guild):
        """Configures a new guild upon joining.

        parameters:
            guild (discord.Guild): the guild that was joined
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Joined guild with ID {guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_update(self, before, after):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_update
        """
        diff = util.get_object_diff(
            before,
            after,
            [
                "banner",
                "banner_url",
                "bitrate_limit",
                "categories",
                "default_role",
                "description",
                "discovery_splash",
                "discovery_splash_url",
                "emoji_limit",
                "emojis",
                "explicit_content_filter",
                "features",
                "icon",
                "icon_url",
                "name",
                "owner",
                "region",
                "roles",
                "rules_channel",
                "verification_level",
            ],
        )

        embed = discord.Embed()
        embed = util.add_diff_fields(embed, diff)
        embed.add_field(name="Server", value=before.name)

        log_channel = await self.get_log_channel_from_guild(
            before, key="guild_events_channel"
        )
        await self.logger.info(
            f"Guild with ID {before.id} updated",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_role_create(self, role):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_create"""
        embed = discord.Embed()
        embed.add_field(name="Server", value=role.guild.name)
        log_channel = await self.get_log_channel_from_guild(
            role.guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"New role with name {role.name} added to guild with ID {role.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_role_delete(self, role):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_delete"""
        embed = discord.Embed()
        embed.add_field(name="Server", value=role.guild.name)
        log_channel = await self.get_log_channel_from_guild(
            role.guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Role with name {role.name} deleted from guild with ID {role.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_role_update(self, before, after):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_update"""
        attrs = ["color", "mentionable", "name", "permissions", "position", "tags"]
        diff = util.get_object_diff(before, after, attrs)

        embed = discord.Embed()
        embed = util.add_diff_fields(embed, diff)
        embed.add_field(name="Server", value=before.name)

        log_channel = await self.get_log_channel_from_guild(
            before.guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Role with name {before.name} updated in guild with ID {before.guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_guild_emojis_update(self, guild, before, _):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_emojis_update
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=before.name)

        log_channel = await self.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.logger.info(
            f"Emojis updated in guild with ID {guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_member_ban(self, guild, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_ban"""
        embed = discord.Embed()
        embed.add_field(name="User", value=user)
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.get_log_channel_from_guild(
            guild, key="member_events_channel"
        )
        await self.logger.info(
            f"User with ID {user.id} banned from guild with ID {guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )

    async def on_member_unban(self, guild, user):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_unban"""
        embed = discord.Embed()
        embed.add_field(name="User", value=user)
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.get_log_channel_from_guild(
            guild, key="member_events_channel"
        )
        await self.logger.info(
            f"User with ID {user.id} unbanned from guild with ID {guild.id}",
            embed=embed,
            send=True,
            channel=log_channel,
        )
