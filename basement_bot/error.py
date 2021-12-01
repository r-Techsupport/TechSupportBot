"""Module for command error responses.
"""
import munch
from discord.ext import commands


class ExtensionDisabled(commands.errors.CheckFailure):
    """The exception thrown when an extension is disabled."""


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
    ExtensionDisabled: ErrorResponse(
        "That extension is disabled for this context/server"
    ),
}

IGNORED_ERRORS = set([commands.CommandNotFound])
