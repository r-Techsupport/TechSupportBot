"""The main bot functions.
"""

import sys

from admin import AdminControl
from config import ConfigAPI
from database import DatabaseAPI
from discord import Game
from discord.channel import DMChannel
from discord.ext.commands import Bot
from error import ErrorAPI
from plugin import PluginAPI
from utils.logger import get_logger

log = get_logger("Basement Bot")


class BasementBot(Bot):
    """The main bot object.

    parameters:
        run (bool): True if the bot should run on instantiation
        validate_config (bool): True if the bot's config should be validated
    """

    def __init__(self, run=True, validate_config=True):
        # the config API will set this
        self.config = None

        self.config_api = ConfigAPI(bot=self, validate=validate_config)
        self.plugin_api = PluginAPI(bot=self)
        self.database_api = DatabaseAPI(bot=self)
        self.error_api = ErrorAPI(bot=self)

        super().__init__(self.config.main.required.command_prefix)

        self.game = (
            self.config.main.optional.game
            if self.config.main.optional.get("game")
            else None
        )

        if run:
            log.debug("Bot starting upon init")
            self.start(self.config.main.required.auth_token)
        else:
            log.debug("Bot created but not started")

    async def on_ready(self):
        """Callback for when the bot is finished starting up."""
        if self.game:
            await self.set_game(self.game)
        log.info(f"Commands available with the `{self.command_prefix}` prefix")

    async def on_message(self, message):
        """Catches messages and acts appropriately.

        parameters:
            message (discord.Message): the message object
        """
        owner = await self.get_owner()

        if (
            owner
            and isinstance(message.channel, DMChannel)
            and message.author.id != owner.id
            and not message.author.bot
        ):
            await owner.send(f'PM from {message.author.mention}: "{message.content}"')

        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def on_error(self, event_method, *args, **kwargs):
        """Catches non-command errors and sends them to the error API for processing.

        parameters:
            event_method (str): the event method associated with the error (eg. message)
        """
        _, exception, _ = sys.exc_info()
        await self.error_api.handle_error(event_method, exception)

    async def on_command_error(self, context, exception):
        """Catches command errors and sends them to the error API for processing.

        parameters:
            context (discord.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        await self.error_api.handle_command_error(context, exception)

    async def set_game(self, game):
        """Sets the Discord activity to a given game.

        parameters:
            game (str): the name of the game to display
        """
        self.game = game
        await self.change_presence(activity=Game(name=self.game))

    # pylint: disable=invalid-overridden-method
    def start(self, *args, **kwargs):
        """Loads initial plugins (blocking) and starts the connection."""
        log.debug("Starting bot...")

        self.plugin_api.load_plugins()

        self.add_cog(AdminControl(self))

        try:
            self.loop.run_until_complete(super().start(*args, **kwargs))
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.logout())
        finally:
            self.loop.close()

    async def get_owner(self):
        """Gets the owner object for the bot application."""
        app_info = await self.application_info()
        return app_info.owner if app_info else None

    async def can_run(self, ctx, *, call_once=False):
        """Wraps the default can_run check to evaluate if a check call is necessary.

        This method wraps the GroupMixin method.

        parameters:
            ctx (discord.Context): the context associated with the command
            call_once (bool): True if the check should be retrieved from the call_once attribute
        """
        is_bot_admin = await self.is_bot_admin(ctx)

        if is_bot_admin:
            return True

        # the user is not a bot admin, so they can't do this
        if ctx.command.cog.ADMIN_ONLY:
            return False

        result = await super().can_run(ctx, call_once=call_once)
        return result

    async def is_bot_admin(self, ctx):
        """Processes command context against admin/owner data.

        Command checks are disabled if the context author is the owner.

        They are also ignored if the author is bot admin in the config.

        parameters:
            ctx (discord.Context): the context associated with the command
        """
        owner = await self.get_owner()
        if getattr(owner, "id", None) == ctx.author.id:
            return True

        if ctx.message.author.id in [int(id) for id in self.config.main.admins.ids]:
            return True

        role_is_admin = False
        for role in getattr(ctx.message.author, "roles", []):
            if role.name in self.config.main.admins.roles:
                role_is_admin = True
                break
        if role_is_admin:
            return True

        return False
