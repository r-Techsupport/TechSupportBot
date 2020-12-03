"""Provides an interface for handling runtime errors.
"""

import discord.ext.commands as error_enum
from api import BotAPI
from discord import Embed, Forbidden
from discord.ext.commands import Cog
from utils.logger import get_logger

log = get_logger("Error")

# pylint: disable=too-few-public-methods
class ErrorMessageTemplate:
    """Object for generating a custom error message from a variable exception.

    parameters:
        message_format (str): the substition formatted (%s) message
        keys: Union[str, list]: the key(s) to be looked up from the exception
    """

    DEFAULT_MESSAGE = "I ran into an error processing your command..."

    def __init__(self, message_format=None, keys=None):
        if keys:
            self.keys = keys if isinstance(keys, list) else [keys]
        else:
            self.keys = []

        self.message_format = message_format

    def get_message(self, exception=None):
        """Gets a message from a given exception.

        If no exception is provided, gets the default message.

        parameters:
            exception (Exception): the exception to reference
        """
        if not self.message_format:
            return self.DEFAULT_MESSAGE

        values = []
        for key in self.keys:
            value = getattr(exception, key, None)
            if not value:
                return self.DEFAULT_MESSAGE
            values.append(value)

        return self.message_format % tuple(values)


class ErrorAPI(BotAPI):
    """API for handling errors.

    parameters:
        bot (BasementBot): the bot object
    """

    CUSTOM_TEMPLATES = {
        error_enum.MissingRequiredArgument: ErrorMessageTemplate(
            "You did not provide the command argument: `%s`", "param"
        ),
        error_enum.TooManyArguments: ErrorMessageTemplate(
            "You provided too many arguments to that command"
        ),
        error_enum.BotMissingAnyRole: ErrorMessageTemplate(
            "I am unable to do that because I lack the permission(s): `%s`",
            "missing_perms",
        ),
        error_enum.UnexpectedQuoteError: ErrorMessageTemplate(
            "I wasn't able to understand your command because of an unexpected quote (%s)",
            "quote",
        ),
        error_enum.InvalidEndOfQuotedStringError: ErrorMessageTemplate(
            "You provided an unreadable char after your quote: `%s`",
            "char",
        ),
        error_enum.ExpectedClosingQuoteError: ErrorMessageTemplate(
            "You did not close your quote with a `%s`",
            "close_quote",
        ),
        error_enum.CheckFailure: ErrorMessageTemplate(
            "You are not allowed to use that command"
        ),
        error_enum.DisabledCommand: ErrorMessageTemplate("That command is disabled"),
        error_enum.CommandOnCooldown: ErrorMessageTemplate(
            "That command is on cooldown for you"
        ),
    }

    IGNORE_ERRORS = set([error_enum.CommandNotFound])

    async def handle_error(self, event_method, exception, context=None):
        """Handles all errors.

        parameters:
            event_method (str): the event method associated with the error (eg. message)
            context (discord.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        if type(exception) in self.IGNORE_ERRORS:
            return

        log.error(exception)

        embed = self.generate_error_embed(event_method, context, exception)

        app_info = await self.bot.application_info()
        try:
            await app_info.owner.send(embed=embed)
        except Forbidden:
            pass

    async def handle_command_error(self, context, exception):
        """Handles command errors, whcih are passed to the main error handler.

        parameters:
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
            if Cog._get_overridden_method(cog.cog_command_error) is not None:
                return
        # end original Discord.py logic

        message_template = self.CUSTOM_TEMPLATES.get(exception.__class__, "")
        # see if we have mapped this error to no response (None)
        # or if we have added it to the global ignore list of errors
        if message_template is None or exception.__class__ in self.IGNORE_ERRORS:
            return
        # otherwise set it a default error message
        if message_template == "":
            message_template = ErrorMessageTemplate()

        error_message = message_template.get_message(exception)

        try:
            await context.author.send(error_message)
        except Forbidden:
            await context.send(f"{context.author.mention} {error_message}")

        context.error_message = error_message
        await self.handle_error("command", exception, context=context)

    def generate_error_embed(self, event_method, context, exception):
        """Wrapper for generating the error embed.

        parameters:
            event_method (str): the event method associated with the error (eg. message)
            context (discord.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        embed = Embed(title="Error! :confounded:")
        embed.add_field(name="Event", value=event_method, inline=False)

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
                name="DM", value=f'*"{getattr(context, "error_message", "*Unknown*")}"*'
            )

        embed.add_field(name="Exception", value=f"```{exception}```", inline=False)
        embed.add_field(name="Type", value=f"`{type(exception)}`", inline=False)
        embed.set_thumbnail(url=self.bot.user.avatar_url)

        return embed
