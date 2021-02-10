"""Module for logging bot events.
"""

import logging
import os
import traceback

import discord
import munch
from discord.ext import commands


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
    # this defaults to True because most logs shouldn't send out
    DEFAULT_LOG_CONSOLE_ONLY = True
    # this defaults to False because most error logs should send out
    DEFAULT_ERROR_LOG_CONSOLE_ONLY = False

    def __init__(self, bot=None, name="root"):
        self.bot = bot

        try:
            self.debug_mode = bool(int(os.environ.get("DEBUG", 0)))
        except ValueError:
            self.debug_mode = False

        # pylint: disable=using-constant-test
        logging.basicConfig(level=logging.DEBUG if self.debug else logging.INFO)

        self.console_logger = logging.getLogger(name)

    async def info(self, message, *args, **kwargs):
        """Logs at the INFO level.

        parameters:
            message (str): the message to log
            console_only (bool): True if only the console should be logged to
            send (bool): The reverse of the above (overrides console_only)
        """
        await self.handle_generic_log(
            message, "info", self.console_logger.info, *args, **kwargs
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

        await self.handle_generic_log(
            message, "debug", self.console_logger.debug, *args, **kwargs
        )

    async def warning(self, message, *args, **kwargs):
        """Logs at the WARNING level.

        parameters:
            message (str): the message to log
            console_only (bool): True if only the console should be logged to
            send (bool): The reverse of the above (overrides console_only)
        """

        await self.handle_generic_log(
            message, "warning", self.console_logger.warning, *args, **kwargs
        )

    async def error(self, message, *args, **kwargs):
        """Logs at the INFO level.

        parameters:
            message (str): the message to log
            console_only (bool): True if only the console should be logged to
            send (bool): The reverse of the above (overrides console_only)
        """

        ctx = kwargs.pop("context", None)
        exception = kwargs.pop("exception", None)
        console_only = self._is_console_only(kwargs, is_error=True)

        self.console_logger.error(message, *args, **kwargs)

        if console_only:
            return

        # command error
        if ctx and exception:
            await self.handle_command_error_log(message, ctx, exception)
            return

        # bot error
        await self.handle_error_log(message, exception)

    async def handle_generic_log(self, message, level, console, *args, **kwargs):
        """Handles most logging contexts.

        parameters:
            message (str): the message to log
            level (str): the logging level
            console (func): logging level method
            console_only (bool): True if only the console should be logged to
            send (bool): The reverse of the above (overrides console_only)
        """
        console_only = self._is_console_only(kwargs, is_error=False)

        console(message, *args, **kwargs)

        if console_only:
            return

        owner = await self.bot.get_owner()
        if not owner:
            return

        embed = self.generate_log_embed(message, level)

        await owner.send(embed=embed)

    def _is_console_only(self, kwargs, is_error):
        """Determines from a kwargs dict if console_only is absolutely True.

        This is so `send` can be provided as a convenience arg.

        parameters:
            kwargs (dict): the kwargs to parse
            is_error (bool): True if the decision is for an error log
        """
        console_only = kwargs.pop(
            "console_only",
            self.DEFAULT_ERROR_LOG_CONSOLE_ONLY
            if is_error
            else self.DEFAULT_LOG_CONSOLE_ONLY,
        )
        send = kwargs.pop(
            "send",
            not (
                self.DEFAULT_ERROR_LOG_CONSOLE_ONLY
                if is_error
                else self.DEFAULT_LOG_CONSOLE_ONLY
            ),
        )

        console_only = False if send else console_only

        return console_only

    async def handle_error_log(self, message, exception, context=None):
        """Handles all error log events.

        parameters:
            message (str): the message associated with the error (eg. on_message)
            exception (Exception): the exception object associated with the error
            context (discord.Context): the context associated with the exception
        """
        if type(exception) in self.IGNORED_ERRORS:
            return

        exception_string = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )

        exception_string = exception_string[:1994]

        embed = self.generate_error_embed(message, context)

        try:
            owner = await self.bot.get_owner()
            if owner:
                await owner.send(embed=embed)
                await owner.send(f"```{exception_string}```")
        except discord.Forbidden:
            pass

    async def handle_command_error_log(self, message, context, exception):
        """Handles command error log events.

        This wraps passing events to the main error handler.

        parameters:
            message (str): the message associated with the error (eg. on_message)
            context (discord.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        #  begin original Discord.py logic
        if self.bot.extra_events.get("on_command_error", None):
            return
        if hasattr(context.command, "on_error"):
            return
        cog = context.cog
        if cog:
            # pylint: disable=protected-access
            if commands.Cog._get_overridden_method(cog.cog_command_error) is not None:
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

        await context.send(f"{context.author.mention} {error_message}")

        context.error_message = error_message
        await self.handle_error_log(message, exception, context=context)

    def generate_log_embed(self, message, level):
        """Wrapper for generated the log embed.

        parameters:
            message (str): the message
            level (str): the logging level
        """
        embed = self.bot.embed_api.Embed(
            title=f"Logging.{level.upper()}", description=message
        )

        embed.set_thumbnail(url=self.bot.user.avatar_url)

        return embed

    def generate_error_embed(self, message, context=None):
        """Wrapper for generating the error embed.

        parameters:
            message (str): the message associated with the error (eg. message)
            context (discord.Context): the context associated with the exception
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
