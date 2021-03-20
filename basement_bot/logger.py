"""Module for logging bot events.
"""

import logging
import os
import traceback
import datetime
import asyncio

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
    DISCORD_WAIT = 2

    def __init__(self, bot=None, name="root", queue=True):
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

        if self.queue_enabled:
            self.bot.loop.create_task(self.log_from_queue())

    async def info(self, message, *args, **kwargs):
        """Logs at the INFO level.

        parameters:
            message (str): the message to log
            console_only (bool): True if only the console should be logged to
            send (bool): The reverse of the above (overrides console_only)
        """

        if self.queue_enabled:
            await self.send_queue.put({
                "level": "info",
                "message": message,
                "args": args,
                "kwargs": kwargs
            })
            return

        await self.handle_generic_log(
            message, "info", self.console.info, *args, **kwargs
        )

    async def debug(self, message, *args, **kwargs):
        """Logs at the DEBUG level.

        parameters:
            message (str): the message to log
            console_only (bool): True if only the console should be logged to
            send (bool): The reverse of the above (overrides console_only)
        """
        if not self.debug_mode:
            return

        if self.queue_enabled:
            await self.send_queue.put({
                "level": "debug",
                "message": message,
                "args": args,
                "kwargs": kwargs
            })
            return

        await self.handle_generic_log(
            message, "debug", self.console.debug, *args, **kwargs
        )

    async def warning(self, message, *args, **kwargs):
        """Logs at the WARNING level.

        parameters:
            message (str): the message to log
            console_only (bool): True if only the console should be logged to
            send (bool): The reverse of the above (overrides console_only)
        """
        if self.queue_enabled:
            await self.send_queue.put({
                "level": "warning",
                "message": message,
                "args": args,
                "kwargs": kwargs
            })
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
            console_only (bool): True if only the console should be logged to
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

        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            pass

    async def event(self, event_type, *args, **kwargs):
        if self.queue_enabled:
            await self.send_queue.put({
                "level": "event",
                "event_type": event_type,
                "args": args,
                "kwargs": kwargs
            })
            return

        await self.handle_event_log(event_type, *args, **kwargs)

    async def handle_event_log(self, event_type, *args, **kwargs):
        console_only = self._is_console_only(kwargs, is_error=False)    

        channel = kwargs.get("channel", None)

        event_data = self.generate_event_data(event_type, *args, **kwargs)

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

        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            pass

    async def error(self, message, *args, **kwargs):
        """Logs at the ERROR level.

        parameters:
            message (str): the message to log
            console_only (bool): True if only the console should be logged to
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        if self.queue_enabled:
            await self.send_queue.put({
                "level": "error",
                "args": args,
                "kwargs": kwargs
            })
            return

        await self.handle_error_log(message, *args, **kwargs)

    async def handle_error_log(self, message, *args, **kwargs):
        ctx = kwargs.get("context", None)
        exception = kwargs.get("exception", None)
        console_only = self._is_console_only(kwargs, is_error=True)

        channel = kwargs.get("channel", None)

        self.console.error(message)

        if console_only:
            return

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
        default_send =  self.DEFAULT_ERROR_LOG_SEND if is_error else self.DEFAULT_LOG_SEND
        return not kwargs.get("send", default_send)

    def generate_event_data(self, event_type, *args, **kwargs):
        message = None
        embed = self.bot.embed_api.Embed()
        embed.set_thumbnail(url=self.bot.user.avatar_url)

        if event_type == "command":
            ctx = kwargs.get("context", kwargs.get("ctx"))

            message = f"Command detected: {ctx.prefix}{ctx.command.name}"
            embed.title = message
            embed.add_field(name="User", value=ctx.author, inline=False)
            embed.add_field(name="Channel", value=ctx.channel.name, inline=False)
            embed.add_field(name="Server", value=f"{ctx.guild.name} ({ctx.guild.id})", inline=False)

        elif event_type == "message_edit":
            before = kwargs.get("before")
            after = kwargs.get("after")

            message = f"Message edit detected on message with ID {before.id}"
            embed.title = message

            embed.add_field(name="Before edit", value=before.content or "None")
            embed.add_field(name="After edit", value=after.content or "None")
            embed.add_field(name="Channel", value=before.channel.name)
            embed.add_field(name="Server", value=f"{before.channel.guild.name} ({before.channel.guild.id})", inline=False)

        else:
            message = f"New event: {event_type}"
            embed.title = message

        return {"message": message, "embed": embed}

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
                inline=True,
            )

        embed.set_thumbnail(url=self.bot.user.avatar_url)

        return embed

    async def log_from_queue(self):
        last_send_to_discord = datetime.datetime.now() - datetime.timedelta(seconds=self.DISCORD_WAIT)

        while True:
            try:
                log_data = await self.send_queue.get()
                if not log_data:
                    continue

                log_data = munch.munchify(log_data)

                is_error = log_data.level == "error"
                if not self._is_console_only(log_data.kwargs, is_error=is_error):
                    # check if we need to sleep before sending to discord again
                    duration = (datetime.datetime.now() - last_send_to_discord).seconds
                    if duration < self.DISCORD_WAIT:
                        await asyncio.sleep(int(self.DISCORD_WAIT-duration))
                    last_send_to_discord = datetime.datetime.now()

                if log_data.level == "info":
                    await self.handle_generic_log(
                        log_data.message, "info", self.console.info, *log_data.args, **log_data.kwargs
                    )
                elif log_data.level == "debug":
                    await self.handle_generic_log(
                        log_data.message, "debug", self.console.debug, *log_data.args, **log_data.kwargs
                    )
                elif log_data.level == "warning":
                    await self.handle_generic_log(
                        log_data.message, "debug", self.console.warning, *log_data.args, **log_data.kwargs
                    )
                elif log_data.level == "event":
                    await self.handle_event_log(
                        log_data.event_type, *log_data.args, **log_data.kwargs
                    )
                elif log_data.level == "error":
                    await self.handle_error_log(
                        log_data.message, *log_data.args, **log_data.kwargs
                    )
                else:
                    self.console.warning(f"Received unprocessable log level: {log_data.level}")

            except Exception as exception:
                self.console.error(f"Could not read from log queue: {exception}")
