"""Module for logging bot events.
"""

import asyncio
import datetime
import logging
import os
import traceback

import discord
import munch
from discord.ext import commands

OVERRIDDEN_MODULES_MAP = {
    "discord": logging.INFO,
    "gino": logging.WARNING,
    "aio_pika": logging.INFO,
}

for module_name, level in OVERRIDDEN_MODULES_MAP.items():
    logging.getLogger(module_name).setLevel(level)

# pylint: disable=unused-argument

# pylint: disable=too-few-public-methods
class ErrorResponse:
    """Object for generating a custom error message from an exception.

    parameters:
        message_format (str): the substition formatted (%s) message
        lookups (Union[str, list]): the lookup objects to reference
    """

    DEFAULT_MESSAGE = "I ran into an error processing your command"

    def __init__(self, message_format=None, lookups=None):
        self.message_format = message_format

        if lookups:
            lookups = lookups if isinstance(lookups, list) else [lookups]
        else:
            lookups = []

        self.lookups = []
        for lookup in lookups:
            try:
                self.lookups.append(munch.munchify(lookup))
            except Exception:
                # abort message formatting
                self.message_format = None

    def get_message(self, exception=None):
        """Gets a message from a given exception.

        If no exception is provided, gets the default message.

        parameters:
            exception (Exception): the exception to reference
        """
        if not self.message_format:
            return self.DEFAULT_MESSAGE

        values = []
        for lookup in self.lookups:
            value = getattr(exception, lookup.key, None)
            if not value:
                return self.DEFAULT_MESSAGE

            if lookup.get("wrapper"):
                try:
                    value = lookup.wrapper(value)
                except Exception:
                    pass

            values.append(value)

        return self.message_format % tuple(values)


class DelayedLog:
    """Represents log data to be sent.

    parameters:
        level (str): the log level (eg. INFO, DEBUG, WARNING, EVENT)
        message (str): the log message
        args (tuple): optional positional arguments
        kwargs (dict): optional keyword arguments
    """

    # pylint: disable=redefined-outer-name
    def __init__(self, level, *args, log_message=None, **kwargs):
        self.level = level
        self.message = log_message
        self.args = args
        self.kwargs = kwargs
        self.kwargs["time"] = datetime.datetime.utcnow()


class BotLogger:
    """Logging channel interface for the bot.

    parameters:
        bot (bot.BasementBot): the bot object
        name (str): the name of the logging channel
        queue (bool): True if a queue should be used for writing logs
    """

    COMMAND_ERROR_RESPONSE_TEMPLATES = {
        # ConversionError
        commands.ConversionError: ErrorResponse(
            "Could not convert argument to: `%s`", {"key": "converter"}
        ),
        # UserInputError
        # These are mostly raised by conversion failure
        commands.MissingRequiredArgument: ErrorResponse(
            "You did not provide the command argument: `%s`", {"key": "param"}
        ),
        commands.TooManyArguments: ErrorResponse(
            "You provided too many arguments to that command"
        ),
        commands.MessageNotFound: ErrorResponse(
            'I couldn\'t find the message: "%s"', {"key": "argument"}
        ),
        commands.MemberNotFound: ErrorResponse(
            'I coudn\'t find the server member: "%s"', {"key": "argument"}
        ),
        commands.UserNotFound: ErrorResponse(
            'I coudn\'t find the user: "%s"', {"key": "argument"}
        ),
        commands.ChannelNotFound: ErrorResponse(
            'I couldn\'t find the channel: "%s"', {"key": "argument"}
        ),
        commands.ChannelNotReadable: ErrorResponse(
            'I can\'t read the channel: "%s"', {"key": "argument"}
        ),
        commands.ChannelNotReadable: ErrorResponse(
            'I can\'t use the color: "%s"', {"key": "argument"}
        ),
        commands.RoleNotFound: ErrorResponse(
            'I couldn\'t find the role: "%s"', {"key": "argument"}
        ),
        commands.BadInviteArgument: ErrorResponse("I can't use that invite"),
        commands.EmojiNotFound: ErrorResponse(
            'I couldn\'t find the emoji: "%s"', {"key": "argument"}
        ),
        commands.PartialEmojiConversionFailure: ErrorResponse(
            'I couldn\'t use the emoji: "%s"', {"key": "argument"}
        ),
        commands.BadBoolArgument: ErrorResponse(
            'I couldn\'t process the boolean: "%s"', {"key": "argument"}
        ),
        commands.UnexpectedQuoteError: ErrorResponse(
            "I wasn't able to understand your command because of an unexpected quote (%s)",
            {"key": "quote"},
        ),
        commands.InvalidEndOfQuotedStringError: ErrorResponse(
            "You provided an unreadable char after your quote: `%s`",
            {"key": "char"},
        ),
        commands.ExpectedClosingQuoteError: ErrorResponse(
            "You did not close your quote with a `%s`",
            {"key": "close_quotes"},
        ),
        # CheckFailure
        commands.CheckFailure: ErrorResponse(
            "That command can't be ran in this context"
        ),
        commands.CheckAnyFailure: ErrorResponse(
            "That command can't be ran in this context"
        ),
        commands.PrivateMessageOnly: ErrorResponse(
            "That's only allowed in private messages"
        ),
        commands.NoPrivateMessage: ErrorResponse(
            "That's only allowed in server channels"
        ),
        commands.NotOwner: ErrorResponse("Only the bot owner can do that"),
        commands.MissingPermissions: ErrorResponse(
            "I am unable to do that because you lack the permission(s): `%s`",
            {"key": "missing_perms"},
        ),
        commands.BotMissingPermissions: ErrorResponse(
            "I am unable to do that because I lack the permission(s): `%s`",
            {"key": "missing_perms"},
        ),
        commands.MissingRole: ErrorResponse(
            "I am unable to do that because you lack the role: `%s`",
            {"key": "missing_role"},
        ),
        commands.BotMissingRole: ErrorResponse(
            "I am unable to do that because I lack the role: `%s`",
            {"key": "missing_role"},
        ),
        commands.MissingAnyRole: ErrorResponse(
            "I am unable to do that because you lack the role(s): `%s`",
            {"key": "missing_roles"},
        ),
        commands.BotMissingAnyRole: ErrorResponse(
            "I am unable to do that because I lack the role(s): `%s`",
            {"key": "missing_roles"},
        ),
        commands.NSFWChannelRequired: ErrorResponse(
            "I can't do that because the target channel is not marked NSFW"
        ),
        # DisabledCommand
        commands.DisabledCommand: ErrorResponse("That command is disabled"),
        # CommandOnCooldown
        commands.CommandOnCooldown: ErrorResponse(
            "That command is on cooldown for you. Try again in %s seconds",
            {"key": "retry_after", "wrapper": int},
        ),
    }

    IGNORED_ERRORS = set([commands.CommandNotFound])
    # this defaults to False because most logs shouldn't send out
    DEFAULT_LOG_SEND = False
    # this defaults to True because most error logs should send out
    DEFAULT_ERROR_LOG_SEND = True

    def __init__(self, bot=None, name="root", queue=True, send=True):
        self.bot = bot

        try:
            self.debug_mode = bool(int(os.environ.get("DEBUG", 0)))
        except ValueError:
            self.debug_mode = False

        # pylint: disable=using-constant-test
        logging.basicConfig(level=logging.DEBUG if self.debug_mode else logging.INFO)

        self.console = logging.getLogger(name)

        self.send_queue = asyncio.Queue(maxsize=1000) if queue else None
        self.queue_enabled = queue

        self.discord_wait = self.bot.config.main.logging.discord_wait_seconds

        self.send = send

        if self.queue_enabled:
            self.bot.loop.create_task(self.log_from_queue())

    async def info(self, message, *args, **kwargs):
        """Logs at the INFO level.

        parameters:
            message (str): the message to log
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        if self.queue_enabled:
            await self.send_queue.put(
                DelayedLog(level="info", log_message=message, *args, **kwargs)
            )
            return

        await self.handle_generic_log(
            message, "info", self.console.info, *args, **kwargs
        )

    async def debug(self, message, *args, **kwargs):
        """Logs at the DEBUG level.

        parameters:
            message (str): the message to log
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        if not self.debug_mode:
            return

        if self.queue_enabled:
            await self.send_queue.put(
                DelayedLog(level="debug", log_message=message, *args, **kwargs)
            )
            return

        await self.handle_generic_log(
            message, "debug", self.console.debug, *args, **kwargs
        )

    async def warning(self, message, *args, **kwargs):
        """Logs at the WARNING level.

        parameters:
            message (str): the message to log
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        if self.queue_enabled:
            await self.send_queue.put(
                DelayedLog(level="warning", log_message=message, *args, **kwargs)
            )
            return

        await self.handle_generic_log(
            message, "warning", self.console.warning, *args, **kwargs
        )

    async def handle_generic_log(self, message, level_, console, *args, **kwargs):
        """Handles most logging contexts.

        parameters:
            message (str): the message to log
            level (str): the logging level
            console (func): logging level method
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        console_only = self._is_console_only(kwargs, is_error=False)

        channel = kwargs.get("channel", None)

        console(message)

        if console_only:
            return

        if channel:
            target = self.bot.get_channel(int(channel))
        else:
            target = await self.bot.get_owner()

        embed = self.generate_log_embed(message, level_)
        embed.timestamp = kwargs.get("time", datetime.datetime.utcnow())

        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            pass

    async def event(self, event_type, *args, **kwargs):
        """Logs at the EVENT level.

        This provides an interface for logging Discord events (eg, on_member_update)

        parameters:
            event_type (str): the event type suffix
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        if self.queue_enabled:
            kwargs["event_type"] = event_type
            await self.send_queue.put(DelayedLog(level="event", *args, **kwargs))
            return

        await self.handle_event_log(event_type, *args, **kwargs)

    async def handle_event_log(self, event_type, *args, **kwargs):
        """Handles event logging.

        parameters:
            event_type (str): the event type suffix
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        console_only = self._is_console_only(kwargs, is_error=False)

        channel = kwargs.get("channel", None)

        event_data = self.generate_event_data(event_type, *args, **kwargs)
        if not event_data:
            return

        message = event_data.get("message")
        if not message:
            return

        # events are a special case of the INFO level
        self.console.info(message)

        if console_only:
            return

        if channel:
            target = self.bot.get_channel(int(channel))
        else:
            target = await self.bot.get_owner()

        embed = event_data.get("embed")
        if not embed:
            return

        embed.timestamp = kwargs.get("time", datetime.datetime.utcnow())

        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            pass

    async def error(self, message, *args, **kwargs):
        """Logs at the ERROR level.

        parameters:
            message (str): the message to log
            exception (Exception): the exception object
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        if self.queue_enabled:
            await self.send_queue.put(
                DelayedLog(level="error", log_message=message, *args, **kwargs)
            )
            return

        await self.handle_error_log(message, *args, **kwargs)

    # pylint: disable=too-many-return-statements,too-many-branches
    async def handle_error_log(self, message, *args, **kwargs):
        """Handles error logging.

        parameters:
            message (str): the message to log with the error
            exception (Exception): the exception object
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        ctx = kwargs.get("context", None)
        exception = kwargs.get("exception", None)
        console_only = self._is_console_only(kwargs, is_error=True)

        channel = kwargs.get("channel", None)

        self.console.error(message)

        # command error
        if ctx and exception:
            #  begin original Discord.py logic
            if self.bot.extra_events.get("on_command_error", None):
                return
            if hasattr(ctx.command, "on_error"):
                return
            cog = ctx.cog
            if cog:
                # pylint: disable=protected-access
                if (
                    commands.Cog._get_overridden_method(cog.cog_command_error)
                    is not None
                ):
                    return
            # end original Discord.py logic

            message_template = self.COMMAND_ERROR_RESPONSE_TEMPLATES.get(
                exception.__class__, ""
            )
            # see if we have mapped this error to no response (None)
            # or if we have added it to the global ignore list of errors
            if message_template is None or exception.__class__ in self.IGNORED_ERRORS:
                return
            # otherwise set it a default error message
            if message_template == "":
                message_template = ErrorResponse()

            error_message = message_template.get_message(exception)

            await ctx.send(f"{ctx.author.mention} {error_message}")

            ctx.error_message = error_message

        if console_only:
            return

        if type(exception) in self.IGNORED_ERRORS:
            return

        exception_string = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )

        print(exception_string)
        exception_string = exception_string[:1994]

        embed = self.generate_error_embed(message, ctx)
        embed.timestamp = kwargs.get("time", datetime.datetime.utcnow())

        if channel:
            target = self.bot.get_channel(int(channel))
        else:
            target = await self.bot.get_owner()

        if not target:
            return

        try:
            await target.send(embed=embed)
            await target.send(f"```{exception_string}```")
        except discord.Forbidden:
            pass

    def _is_console_only(self, kwargs, is_error):
        """Determines from a kwargs dict if console_only is absolutely True.

        This is so `send` can be provided as a convenience arg.

        parameters:
            kwargs (dict): the kwargs to parse
            is_error (bool): True if the decision is for an error log
        """
        # check if sending is disabled globally
        if not self.send:
            return True

        default_send = (
            self.DEFAULT_ERROR_LOG_SEND if is_error else self.DEFAULT_LOG_SEND
        )

        return not kwargs.get("send", default_send)

    # pylint: disable=inconsistent-return-statements
    def generate_event_data(self, event_type, *args, **kwargs):
        """Generates an event message and embed.

        parameters:
            event_type (str): the event type suffix
        """
        message = None
        embed = None

        # hacky AF but I love it
        render_func_name = f"render_{event_type}_event"
        render_func = getattr(self, render_func_name, self.render_default_event)

        kwargs["event_type"] = event_type

        try:
            message, embed = render_func(*args, **kwargs)
        except Exception as exception:
            self.console.error(
                f"Could not render event data: {exception} (using default render)"
            )
            message, embed = self.render_default_event(*args, **kwargs)

        if embed:
            embed.set_thumbnail(url=self.bot.user.avatar_url)

        return {"message": message, "embed": embed}

    def render_default_event(self, *args, **kwargs):
        """Renders the message and embed for the default case."""
        event_type = kwargs.get("event_type")

        message = f"New event: {event_type}"
        embed = self.bot.embed_api.Embed(title=message)

        return message, embed

    def render_command_event(self, *args, **kwargs):
        """Renders the named event."""
        ctx = kwargs.get("context", kwargs.get("ctx"))
        server_text = self.get_server_text(ctx)

        sliced_content = ctx.message.content[0:255]
        message = f"Command detected: {sliced_content}"

        embed = self.bot.embed_api.Embed(
            title="Command detected", description=sliced_content
        )
        embed.add_field(name="User", value=ctx.author)
        embed.add_field(name="Channel", value=getattr(ctx.channel, "name", "DM"))
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_message_delete_event(self, *args, **kwargs):
        """Renders the named event."""
        message_object = kwargs.get("message")
        server_text = self.get_server_text(message_object)

        message = f"Message with ID {message_object.id} deleted"

        embed = self.bot.embed_api.Embed(title="Message deleted", description=message)
        embed.add_field(name="Content", value=message_object.content or "None")
        embed.add_field(name="Author", value=message_object.author)
        embed.add_field(
            name="Channel",
            value=getattr(message_object.channel, "name", "DM"),
        )
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_message_edit_event(self, *args, **kwargs):
        """Renders the named event."""
        before = kwargs.get("before")
        after = kwargs.get("after")

        attrs = ["content", "embeds"]
        diff = self.get_object_diff(before, after, attrs)

        server_text = self.get_server_text(before.channel)

        message = f"Message edit detected on message with ID {before.id}"

        if diff:
            embed_title = (
                ",".join(k.upper() for k in diff) + " updated for message"
            )
        else:
            embed_title = "Message updated"
        embed = self.bot.embed_api.Embed(title=embed_title, description=message)

        embed = self.add_diff_fields(embed, diff)

        embed.add_field(name="Author", value=before.author)
        embed.add_field(name="Channel", value=getattr(before.channel, "name", "DM"))
        embed.add_field(
            name="Server",
            value=server_text,
        )

        return message, embed

    def render_bulk_message_delete_event(self, *args, **kwargs):
        """Renders the named event."""
        messages = kwargs.get("messages")

        unique_channels = set()
        unique_servers = set()
        for message in messages:
            unique_channels.add(message.channel.name)
            unique_servers.add(
                f"{message.channel.guild.name} ({message.channel.guild.id})"
            )

        message = f"{len(messages)} messages bulk deleted!"

        embed = self.bot.embed_api.Embed(
            title="Bulk message delete", description=message
        )
        embed.add_field(name="Channels", value=",".join(unique_channels))
        embed.add_field(name="Servers", value=",".join(unique_servers))

        return message, embed

    def render_reaction_add_event(self, *args, **kwargs):
        """Renders the named event."""
        reaction = kwargs.get("reaction")
        user = kwargs.get("user")
        server_text = self.get_server_text(reaction.message.channel)

        message = f"Reaction added to message with ID {reaction.message.id} by user with ID {user.id}"

        embed = self.bot.embed_api.Embed(title="Reaction added", description=message)
        embed.add_field(name="Emoji", value=reaction.emoji)
        embed.add_field(name="User", value=user)
        embed.add_field(name="Message", value=reaction.message.content or "None")
        embed.add_field(name="Message Author", value=reaction.message.author)
        embed.add_field(
            name="Channel", value=getattr(reaction.message.channel, "name", "DM")
        )
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_reaction_remove_event(self, *args, **kwargs):
        """Renders the named event."""
        reaction = kwargs.get("reaction")
        user = kwargs.get("user")
        server_text = self.get_server_text(reaction.message.channel)

        message = f"Reaction removed from message with ID {reaction.message.id} by user with ID {user.id}"

        embed = self.bot.embed_api.Embed(title="Reaction removed", description=message)
        embed.add_field(name="Emoji", value=reaction.emoji)
        embed.add_field(name="User", value=user)
        embed.add_field(name="Message", value=reaction.message.content or "None")
        embed.add_field(name="Message Author", value=reaction.message.author)
        embed.add_field(
            name="Channel", value=getattr(reaction.message.channel, "name", "DM")
        )
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_reaction_clear_event(self, *args, **kwargs):
        """Renders the named event."""
        message = kwargs.get("message")
        reactions = kwargs.get("reactions")
        server_text = self.get_server_text(message.channel)

        message = f"{len(reactions)} cleared from message with ID {message.id}"

        unique_emojis = set()
        for reaction in reactions:
            unique_emojis.add(reaction.emoji)

        embed = self.bot.embed_api.Embed(title="Reactions cleared", description=message)
        embed.add_field(name="Emojis", value=",".join(unique_emojis))
        embed.add_field(name="Message", value=message.content or "None")
        embed.add_field(name="Message Author", value=message.author)
        embed.add_field(name="Channel", value=getattr(message.channel, "name", "DM"))
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_channel_delete_event(self, *args, **kwargs):
        """Renders the named event."""
        channel = kwargs.get("channel_")
        server_text = self.get_server_text(channel)

        message = (
            f"Channel with ID {channel.id} deleted in guild with ID {channel.guild.id}"
        )

        embed = self.bot.embed_api.Embed(title="Channel deleted", description=message)

        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_channel_create_event(self, *args, **kwargs):
        """Renders the named event."""
        channel = kwargs.get("channel_")
        server_text = self.get_server_text(channel)

        message = (
            f"Channel with ID {channel.id} created in guild with ID {channel.guild.id}"
        )

        embed = self.bot.embed_api.Embed(title="Channel created", description=message)

        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_channel_update_event(self, *args, **kwargs):
        """Renders the named event."""
        before = kwargs.get("before")
        after = kwargs.get("after")
        server_text = self.get_server_text(before)

        attrs = [
            "category",
            "changed_roles",
            "name",
            "overwrites",
            "permissions_synced",
            "position",
        ]
        diff = self.get_object_diff(before, after, attrs)

        message = (
            f"Channel with ID {before.id} modified in guild with ID {before.guild.id}"
        )

        if diff:
            embed_title = (
                ",".join(k.upper() for k in diff) + " updated for channel"
            )
        else:
            embed_title = "Channel updated"

        embed = self.bot.embed_api.Embed(title=embed_title, description=message)

        embed = self.add_diff_fields(embed, diff)

        embed.add_field(name="Channel Name", value=before.name)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_channel_pins_update_event(self, *args, **kwargs):
        """Renders the named event."""
        channel = kwargs.get("channel_")
        # last_pin = kwargs.get("last_pin")
        server_text = self.get_server_text(channel)

        message = f"Channel pins updated in channel with ID {channel.id} in guild with ID {channel.guild.id}"

        embed = self.bot.embed_api.Embed(
            title="Channel pins updated", description=message
        )

        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_integrations_update_event(self, *args, **kwargs):
        """Renders the named event."""
        guild = kwargs.get("guild")
        server_text = self.get_server_text(None, guild=guild)

        message = f"Integrations updated in guild with ID {guild.id}"

        embed = self.bot.embed_api.Embed(
            title="Integrations updated", description=message
        )
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_webhooks_update_event(self, *args, **kwargs):
        """Renders the named event."""
        channel = kwargs.get("channel_")
        server_text = self.get_server_text(channel)

        message = f"Webooks updated for channel with ID {channel.id} in guild with ID {channel.guild.id}"

        embed = self.bot.embed_api.Embed(title="Webhooks updated", description=message)
        embed.add_field(name="Channel", value=channel.name)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_member_join_event(self, *args, **kwargs):
        """Renders the named event."""
        member = kwargs.get("member")
        server_text = self.get_server_text(member)

        message = (
            f"Member with ID {member.id} has joined guild with ID {member.guild.id}"
        )
        embed = self.bot.embed_api.Embed(
            title="Member joined guild", description=message
        )

        embed.add_field(name="Member", value=member)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_member_remove_event(self, *args, **kwargs):
        """Renders the named event."""
        member = kwargs.get("member")
        server_text = self.get_server_text(member)

        message = f"Member with ID {member.id} has left guild with ID {member.guild.id}"
        embed = self.bot.embed_api.Embed(
            title="Member removed from guild", description=message
        )

        embed.add_field(name="Member", value=member)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_member_update_event(self, *args, **kwargs):
        """Renders the named event."""
        before = kwargs.get("before")
        after = kwargs.get("after")
        server_text = self.get_server_text(before)

        attrs = ["activity", "avatar_url", "avatar", "nick", "roles", "status"]
        diff = self.get_object_diff(before, after, attrs)

        message = (
            f"Member with ID {before.id} was updated in guild with ID {before.guild.id}"
        )

        if diff:
            embed_title = (
                ",".join(k.upper() for k in diff) + " updated for member"
            )
        else:
            embed_title = "Member updated"
        embed = self.bot.embed_api.Embed(title=embed_title, description=message)

        embed = self.add_diff_fields(embed, diff)

        embed.add_field(name="Member", value=before)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_join_event(self, *args, **kwargs):
        """Renders the named event."""
        guild = kwargs.get("guild")
        server_text = self.get_server_text(None, guild=guild)

        message = f"Joined guild with ID {guild.id}"

        embed = self.bot.embed_api.Embed(title="Guild joined", description=message)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_remove_event(self, *args, **kwargs):
        """Renders the named event."""
        guild = kwargs.get("guild")
        server_text = self.get_server_text(None, guild=guild)

        message = f"Left guild with ID {guild.id}"

        embed = self.bot.embed_api.Embed(title="Guild left", description=message)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_update_event(self, *args, **kwargs):
        """Renders the named event."""
        before = kwargs.get("before")
        after = kwargs.get("after")
        server_text = self.get_server_text(None, guild=before)

        attrs = [
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
        ]
        diff = self.get_object_diff(before, after, attrs)

        message = f"Guild with ID {before.id} updated"

        if diff:
            embed_title = (
                ",".join(k.upper() for k in diff) + " updated for guild"
            )
        else:
            embed_title = "Guild updated"
        embed = self.bot.embed_api.Embed(title=embed_title, description=message)

        embed = self.add_diff_fields(embed, diff)

        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_role_create_event(self, *args, **kwargs):
        """Renders the named event."""
        role = kwargs.get("role")
        server_text = self.get_server_text(role)

        message = (
            f"New role with name {role.name} added to guild with ID {role.guild.id}"
        )

        embed = self.bot.embed_api.Embed(title="Role created", description=message)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_role_delete_event(self, *args, **kwargs):
        """Renders the named event."""
        role = kwargs.get("role")
        server_text = self.get_server_text(role)

        message = (
            f"Role with name {role.name} deleted from guild with ID {role.guild.id}"
        )

        embed = self.bot.embed_api.Embed(title="Role deleted", description=message)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_role_update_event(self, *args, **kwargs):
        """Renders the named event."""
        before = kwargs.get("before")
        after = kwargs.get("after")
        server_text = self.get_server_text(before)

        attrs = ["color", "mentionable", "name", "permissions", "position", "tags"]
        diff = self.get_object_diff(before, after, attrs)

        message = (
            f"Role with name {before.name} updated in guild with ID {before.guild.id}"
        )

        if diff:
            embed_title = ",".join(k.upper() for k in diff) + " updated for role"
        else:
            embed_title = "Role updated"

        embed = self.bot.embed_api.Embed(title=embed_title, description=message)

        embed = self.add_diff_fields(embed, diff)

        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_guild_emojis_update_event(self, *args, **kwargs):
        """Renders the named event."""
        guild = kwargs.get("guild")
        # before = kwargs.get("before")
        # after = kwargs.get("after")
        server_text = self.get_server_text(None, guild=guild)

        message = f"Emojis updated in guild with ID {guild.id}"

        embed = self.bot.embed_api.Embed(
            title="Guild emojis updated", description=message
        )
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_member_ban_event(self, *args, **kwargs):
        """Renders the named event."""
        guild = kwargs.get("guild")
        user = kwargs.get("user")
        server_text = self.get_server_text(None, guild=guild)

        message = f"User with ID {user.id} banned from guild with ID {guild.id}"

        embed = self.bot.embed_api.Embed(title="Member banned", description=message)
        embed.add_field(name="User", value=user)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    def render_member_unban_event(self, *args, **kwargs):
        """Renders the named event."""
        guild = kwargs.get("guild")
        user = kwargs.get("user")
        server_text = self.get_server_text(None, guild=guild)

        message = f"User with ID {user.id} unbanned from guild with ID {guild.id}"

        embed = self.bot.embed_api.Embed(title="Member unbanned", description=message)
        embed.add_field(name="User", value=user)
        embed.add_field(name="Server", value=server_text)

        return message, embed

    @staticmethod
    def get_server_text(upper_object, guild=None):
        """Gets the embed text for a guild.

        parameters:
            upper_object (obj): the object to pull the guild from
            guild (discord.Guild): the guild to use instead of an upper object
        """
        guild = guild or getattr(upper_object, "guild", None)
        return f"{guild.name} ({guild.id})" if guild else "DM"

    @staticmethod
    def get_object_diff(before, after, attrs_to_check):
        """Finds differences in before, after object pairs.

        before (obj): the before object
        after (obj): the after object
        attrs_to_check (list): the attributes to compare
        """
        result = {}

        for attr in attrs_to_check:
            after_value = getattr(after, attr, None)
            if not after_value:
                continue

            before_value = getattr(before, attr, None)
            if not before_value:
                continue

            if before_value != after_value:
                result[attr] = munch.munchify(
                    {"before": before_value, "after": after_value}
                )

        return result

    @staticmethod
    def add_diff_fields(embed, diff):
        """Adds fields to an embed based on diff data.

        parameters:
            embed (discord.Embed): the embed object
            diff (dict): the diff data for an object
        """
        for attr, diff_data in diff.items():
            attru = attr.upper()
            if isinstance(diff_data.before, list):
                action = (
                    "added"
                    if len(diff_data.before) < len(diff_data.after)
                    else "removed"
                )
                list_diff = set(diff_data.after) ^ set(diff_data.before)

                embed.add_field(
                    name=f"{attru} {action}", value=",".join(str(o) for o in list_diff)
                )
                continue

            embed.add_field(name=f"{attru} (before)", value=diff_data.before)
            embed.add_field(name=f"{attru} (after)", value=diff_data.after)

        return embed

    def generate_log_embed(self, message, level_):
        """Wrapper for generated the log embed.

        parameters:
            message (str): the message
            level (str): the logging level
        """
        embed = self.bot.embed_api.Embed(
            title=f"Logging.{level_.upper()}", description=message
        )

        embed.set_thumbnail(url=self.bot.user.avatar_url)

        return embed

    def generate_error_embed(self, message, context=None):
        """Wrapper for generating the error embed.

        parameters:
            message (str): the message associated with the error (eg. message)
            context (discord.ext.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        embed = self.bot.embed_api.Embed(title="Logging.ERROR", description=message)

        # inject context data if relevant
        if context:
            command = getattr(context, "command", object())
            cog = getattr(command, "cog", object())
            user = getattr(context, "author", object())

            embed.add_field(
                name="Plugin",
                value=getattr(cog, "PLUGIN_NAME", "*Unknown*"),
                inline=False,
            )
            embed.add_field(
                name="Cog",
                value=getattr(cog, "qualified_name", "*Unknown*"),
                inline=False,
            )
            embed.add_field(
                name="Command",
                value=getattr(command, "name", "*Unknown*"),
                inline=False,
            )
            embed.add_field(
                name="User",
                value=getattr(user, "mention", None)
                or getattr(user, "display_name", "*Unknown*"),
                inline=False,
            )
            embed.add_field(
                name="Response",
                value=f'*"{getattr(context, "error_message", "*Unknown*")}"*',
            )

        embed.set_thumbnail(url=self.bot.user.avatar_url)

        return embed

    async def log_from_queue(self):
        """Logs from the in-memory log queue.

        This provides an easier way of handling log throughput to Discord.
        """

        last_send_to_discord = datetime.datetime.now() - datetime.timedelta(
            seconds=self.discord_wait
        )

        while True:
            try:
                log_data = await self.send_queue.get()
                if not log_data:
                    continue

                is_error = log_data.level == "error"
                if not self._is_console_only(log_data.kwargs, is_error=is_error):
                    # check if we need to sleep before sending to discord again
                    duration = (datetime.datetime.now() - last_send_to_discord).seconds
                    if duration < self.discord_wait:
                        await asyncio.sleep(int(self.discord_wait - duration))
                    last_send_to_discord = datetime.datetime.now()

                if log_data.level == "info":
                    await self.handle_generic_log(
                        log_data.message,
                        "info",
                        self.console.info,
                        *log_data.args,
                        **log_data.kwargs,
                    )

                elif log_data.level == "debug":
                    await self.handle_generic_log(
                        log_data.message,
                        "debug",
                        self.console.debug,
                        *log_data.args,
                        **log_data.kwargs,
                    )

                elif log_data.level == "warning":
                    await self.handle_generic_log(
                        log_data.message,
                        "warning",
                        self.console.warning,
                        *log_data.args,
                        **log_data.kwargs,
                    )

                elif log_data.level == "event":
                    event_type = log_data.kwargs.pop("event_type", None)
                    if not event_type:
                        raise AttributeError(
                            "Unable to get event_type from event log data"
                        )

                    await self.handle_event_log(
                        event_type, *log_data.args, **log_data.kwargs
                    )

                elif log_data.level == "error":
                    await self.handle_error_log(
                        log_data.message, *log_data.args, **log_data.kwargs
                    )

                else:
                    self.console.warning(
                        f"Received unprocessable log level: {log_data.level}"
                    )

            except Exception as exception:
                self.console.error(f"Could not read from log queue: {exception}")
