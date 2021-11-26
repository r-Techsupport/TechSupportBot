"""The main bot functions.
"""
import datetime
import os
import re
import sys

import base
import cogs as builtin_cogs
import discord
import error
import util
from discord.ext import commands, ipc


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class BasementBot(base.AdvancedBot):
    """The main bot object.

    parameters:
        run_on_init (bool): True if the bot should run on instantiation
    """

    IPC_SECRET_ENV_KEY = "IPC_SECRET"
    CONFIRM_YES_EMOJI = "✅"
    CONFIRM_NO_EMOJI = "❌"
    PAGINATE_LEFT_EMOJI = "⬅️"
    PAGINATE_RIGHT_EMOJI = "➡️"
    PAGINATE_STOP_EMOJI = "⏹️"
    PAGINATE_DELETE_EMOJI = "🗑️"

    # pylint: disable=attribute-defined-outside-init
    def __init__(self, *args, **kwargs):
        run_on_init = kwargs.pop("run_on_init", None)

        self.owner = None
        self._startup_time = None
        self.ipc = None
        self.builtin_cogs = []

        super().__init__(*args, **kwargs)

        if run_on_init:
            self.run(self.file_config.main.auth_token)

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

        await self.logger.debug("Loading extensions...")
        self.load_extensions()

        if self.db:
            await self.logger.debug("Syncing Postgres tables...")
            await self.db.gino.create_all()

        await self.logger.debug("Loading Help commands...")
        self.remove_command("help")
        help_cog = builtin_cogs.Helper(self)
        self.add_cog(help_cog)

        await self.load_builtin_cog(builtin_cogs.AdminControl)
        await self.load_builtin_cog(builtin_cogs.ConfigControl)
        await self.load_builtin_cog(builtin_cogs.Raw)

        if self.ipc:
            await self.load_builtin_cog(builtin_cogs.IPCEndpoints)

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
