"""Module for the main bot object.
"""

from discord import Game
from discord.ext.commands import Bot

from loader import PluginLoader
from logger import get_logger

log = get_logger("Basement Bot")


class BasementBot(Bot):
    """Defines initialization and event handlers.

    parameters:
        command_prefix (str): the prefix for commands
        game (str): the game title to display
    """

    def __init__(self, command_prefix, game=None):
        if command_prefix == "?":
            command_prefix = "."
        self.command_prefix = command_prefix
        self.game = game
        super().__init__(command_prefix)

        self.plugin_loader = PluginLoader(self)
        self.plugin_loader.load_plugins()

    async def on_ready(self):
        """Runs final setup steps.
        """
        if self.game:
            await self.change_presence(activity=Game(name=self.game))
        log.info(f"Initialization complete")
        log.info(f"Commands available with the `{self.command_prefix}` prefix")
