"""Module for the main bot object.
"""
import logging
import os

from discord import Game
from discord.ext.commands import Bot

from plugin import PluginLoader


class BasementBot(Bot):
    """Defines initialization and event handlers.

    parameters:
        command_prefix (str): the prefix for commands
        debug (bool): True if debug mode enabled
        game (str): the game title to display
    """

    def __init__(self, command_prefix, debug, game=None):
        self.command_prefix = command_prefix
        self.debug = debug
        self.game = game
        super().__init__(command_prefix)

        self._set_logging()

        self.plugin_loader = PluginLoader(self)
        self.plugin_loader.load_plugins()

    async def on_ready(self):
        """Runs final setup steps.
        """
        if self.game:
            await self.change_presence(activity=Game(name=self.game))
        logging.info(f"Initialization complete")
        logging.info(f"Commands available with the `{self.command_prefix}` prefix")

    def _set_logging(self):
        """Sets logging level.
        """
        logging.getLogger().setLevel(logging.DEBUG if self.debug else logging.INFO)
        logging.debug("Debug logging enabled")
