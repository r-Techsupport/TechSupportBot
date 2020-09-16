"""The main bot functions.
"""

import asyncio

import munch
import yaml
from discord import Game
from discord.ext.commands import Bot

from database import DatabaseAPI
from plugin import PluginAPI
from utils.logger import get_logger

log = get_logger("Basement Bot")


class BasementBot(Bot):
    """The main bot object.
    """

    CONFIG_PATH = "./config.yaml"

    def __init__(self, run=True):
        self.config = self._load_config(validate=True)
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

    def _load_config(self, validate):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH) as iostream:
            config = yaml.safe_load(iostream)
        self.config = munch.munchify(config)

        self.config.main.disabled_plugins = self.config.main.disabled_plugins or []

        if validate:
            self._validate_config()

        return self.config

    def _validate_config(self):
        """Loops through defined sections of bot config to check for missing values.
        """

        def check_all(section, subsections):
            for sub in subsections:
                for key, value in self.config.get(section, {}).get(sub, {}).items():
                    error_key = None
                    if value is None:
                        error_key = key
                    elif isinstance(value, dict):
                        for k, v in value.items():
                            if v is None:
                                error_key = k
                    if error_key:
                        if section == "plugins":
                            log.warning(
                                f"Disabling loading of plugin {sub} due to missing config key {error_key}"
                            )
                            # disable the plugin if we can't get its config
                            self.config.main.disabled_plugins.append(sub)
                        else:
                            raise ValueError(
                                f"Config key {error_key} from {section}.{sub} not supplied"
                            )

        check_all("main", ["required", "database"])
        check_all("plugins", list(self.config.plugins.keys()))
