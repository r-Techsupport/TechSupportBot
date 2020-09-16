"""The main bot functions.
"""

import asyncio

import munch
import yaml
from discord import Game
from discord.ext.commands import Bot

from config import ConfigAPI
from database import DatabaseAPI
from plugin import PluginAPI
from utils.logger import get_logger

log = get_logger("Basement Bot")


class BasementBot(Bot):
    """The main bot object.
    """

    CONFIG_PATH = "./config.yaml"

    def __init__(self, run=True):
        self.config = self._load_config()
        super().__init__(self.config.main.required.command_prefix)

        self.game = (
            self.config.main.optional.game
            if self.config.main.optional.get("game")
            else None
        )

        self.plugin_api = PluginAPI(bot=self)
        self.database_api = DatabaseAPI(bot=self)

        if run:
            self.start(self.config.main.required.auth_token)

    async def on_ready(self):
        """Callback for when the bot is finished starting up.
        """
        if self.game:
            await self.set_game(self.game)
        log.info(f"Commands available with the `{self.command_prefix}` prefix")

    async def set_game(self, game):
        """Sets the Discord activity to a given game.

        parameters:
            game (str): the name of the game to display
        """
        self.game = game
        await self.change_presence(activity=Game(name=self.game))

    def start(self, token):
        """Loads initial plugins (blocking) and starts the connection.
        """
        self.plugin_api.load_plugins()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(super().start(token))

    async def shutdown(self):
        """Cleans up for final shutdown of bot instance.
        """
        await self.logout()

    def _load_config(self):
        with open(self.CONFIG_PATH) as iostream:
            config = yaml.safe_load(iostream)
        for key, value in config.get("main", {}).get("required", {}).items():
            if not value:
                raise ValueError(f"Required config {key} not supplied")
        self.config = munch.munchify(config)
        return self.config
