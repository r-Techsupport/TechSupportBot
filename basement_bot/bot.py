"""The main bot functions.
"""

from discord import Game
from discord.ext.commands import Bot

from database import DatabaseAPI
from plugin import PluginAPI
from utils.logger import get_logger

log = get_logger("Basement Bot")


class BasementBot(Bot):
    """The main bot object.

    parameters:
        command_prefix (str): the prefix for commands
        game (str): the game title to display
    """

    def __init__(self, prefix, game=None):
        super().__init__(prefix)
        self.game = game
        self.plugin_api = PluginAPI(bot=self)
        self.database_api = DatabaseAPI(bot=self)

    async def on_ready(self):
        """Callback for when the bot is finished starting up.
        """
        await self.set_game(self.game)
        log.info(f"Commands available with the `{self.command_prefix}` prefix")

    async def set_game(self, game):
        """Sets the Discord activity to a given game.

        parameters:
            game (str): the name of the game to display
        """
        self.game = game
        await self.change_presence(activity=Game(name=self.game))

    async def start(self, *args, **kwargs):
        """Loads initial plugins (blocking) and starts the connection.
        """
        self.plugin_api.load_plugins()
        await super().start(*args, **kwargs)

    async def shutdown(self):
        """Cleans up for final shutdown of bot instance.
        """
        await self.logout()
