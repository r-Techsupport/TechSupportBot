"""Module for command error responses."""

from __future__ import annotations

from typing import Any, Self

import munch
from discord import app_commands
from discord.ext import commands


class ExtensionDisabled(commands.errors.CheckFailure):
    """The exception thrown when an extension is disabled."""

    def __init__(self: Self) -> None:
        self.dont_print_trace = True


class AppCommandExtensionDisabled(app_commands.CheckFailure):
    """The exception thrown when an extension is disabled."""

    def __init__(self: Self) -> None:
        self.dont_print_trace = True


class CommandRateLimit(commands.errors.CheckFailure):
    """The exception thrown when a user is on rate limit"""

    def __init__(self: Self) -> None:
        self.dont_print_trace = True


class AppCommandRateLimit(app_commands.CheckFailure):
    """The exception thrown when a user is on rate limit"""

    def __init__(self: Self) -> None:
        self.dont_print_trace = True


class FactoidNotFoundError(commands.errors.CommandError):
    """Thrown when a factoid is not found.

    Args:
        factoid (str): The name of the factoid that couldn't be found
    """

    def __init__(self: Self, factoid: str) -> None:
        self.dont_print_trace = True
        self.argument = factoid


class TooLongFactoidMessageError(commands.errors.CommandError):
    """Thrown when a message is too long"""

    def __init__(self: Self) -> None:
        self.dont_print_trace = False


class HTTPRateLimit(commands.errors.CommandError):
    """An API call is on rate limit

    Args:
        wait (int): The amount of seconds left until the rate limit expires
    """

    def __init__(self: Self, wait: int) -> None:
        self.wait = wait


class ErrorResponse:
    """Object for generating a custom error message from an exception.

    Attrs:
        DEFAULT_MESSAGE (str): The default error message for unclassified errors

    Args:
        message_format (str): the substition formatted (%s) message
        lookups (str | list[Any]): the lookup objects to reference
        dont_print_trace (bool): If true, the stack trace generated will not be logged
    """

    DEFAULT_MESSAGE = "I ran into an error processing your command"

    def __init__(
        self: Self,
        message_format: str = None,
        lookups: str | list[Any] = None,
        dont_print_trace: bool = False,
    ) -> None:
        self.message_format = message_format
        self.dont_print_trace = dont_print_trace

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

    def default_message(self: Self, exception: Exception = None) -> str:
        """Handles default message generation.

        Args:
            exception (Exception): the exception to reference

        Returns:
            str: The string message to print to the user representing the exception
        """
        return (
            f"{self.DEFAULT_MESSAGE}: *{exception}*"
            if exception
            else self.DEFAULT_MESSAGE
        )

    def get_message(self: Self, exception: Exception = None) -> str:
        """Gets a response message from a given exception.

        Args:
            exception (Exception): the exception to reference

        Returns:
            str: The formatted message filling in any variables from the exception
        """
        if not self.message_format:
            return self.default_message(exception=exception)

        values = []
        for lookup in self.lookups:
            value = getattr(exception, lookup.key, None)
            if not value:
                return self.default_message(exception=exception)

            if lookup.get("wrapper"):
                try:
                    value = lookup.wrapper(value)
                except Exception:
                    pass

            values.append(value)

        return self.message_format % tuple(values)


COMMAND_ERROR_RESPONSES = {
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
        "I couldn't find the message: `%s`", {"key": "argument"}
    ),
    commands.MemberNotFound: ErrorResponse(
        "I couldn't find the server member: `%s`", {"key": "argument"}
    ),
    commands.UserNotFound: ErrorResponse(
        "I couldn't find the user: `%s`", {"key": "argument"}
    ),
    commands.ChannelNotFound: ErrorResponse(
        "I couldn't find the channel: `%s`", {"key": "argument"}
    ),
    commands.ChannelNotReadable: ErrorResponse(
        "I can't read the channel: `%s`", {"key": "argument"}
    ),
    commands.BadColourArgument: ErrorResponse(
        "I can't use the color: `%s`", {"key": "argument"}
    ),
    commands.RoleNotFound: ErrorResponse(
        "I couldn't find the role: `%s`", {"key": "argument"}
    ),
    commands.BadInviteArgument: ErrorResponse("I can't use that invite"),
    commands.EmojiNotFound: ErrorResponse(
        "I couldn't find the emoji: `%s`", {"key": "argument"}
    ),
    commands.PartialEmojiConversionFailure: ErrorResponse(
        "I couldn't use the emoji: `%s`", {"key": "argument"}
    ),
    commands.BadBoolArgument: ErrorResponse(
        "I couldn't process the boolean: `%s`", {"key": "argument"}
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
    commands.CheckFailure: ErrorResponse("That command can't be ran in this context"),
    commands.CheckAnyFailure: ErrorResponse(
        "That command can't be ran in this context"
    ),
    commands.PrivateMessageOnly: ErrorResponse(
        "That's only allowed in private messages"
    ),
    commands.NoPrivateMessage: ErrorResponse("That's only allowed in server channels"),
    commands.NotOwner: ErrorResponse("Only the bot owner can do that"),
    commands.MissingPermissions: ErrorResponse(
        "I am unable to do that because you lack the permission(s): `%s`",
        {"key": "missing_perms"},
    ),
    app_commands.MissingPermissions: ErrorResponse(
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
    commands.DisabledCommand: ErrorResponse("That command is disabled"),
    commands.CommandOnCooldown: ErrorResponse(
        "That command is on cooldown. Try again in %.2f seconds",
        {"key": "retry_after", "wrapper": float},
    ),
    HTTPRateLimit: ErrorResponse(
        "That API is on cooldown. Try again in %.2f seconds",
        {"key": "wait"},
    ),
    # -Custom errors-
    FactoidNotFoundError: ErrorResponse(
        "I couldn't find the factoid `%s`", {"key": "argument"}
    ),
    TooLongFactoidMessageError: ErrorResponse(
        "The raw factoid message contents cannot be more than 2000 characters long!"
    ),
    ExtensionDisabled: ErrorResponse(
        "That extension is disabled for this context/server"
    ),
    CommandRateLimit: ErrorResponse("You are being rate limited for spamming commands"),
    AppCommandExtensionDisabled: ErrorResponse(
        "That extension is disabled for this context/server"
    ),
    AppCommandRateLimit: ErrorResponse(
        "You are being rate limited for spamming commands"
    ),
}

IGNORED_ERRORS = set([commands.CommandNotFound, app_commands.CommandNotFound])
