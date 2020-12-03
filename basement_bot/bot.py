"""The main bot functions.
"""

import sys

import munch
import yaml
from database import DatabaseAPI
from discord import Game
from discord.ext.commands import Bot
from error import ErrorAPI
from plugin import PluginAPI
from utils.logger import get_logger

log = get_logger("Basement Bot")


class BasementBot(Bot):
    """The main bot object."""

    CONFIG_PATH = "./config.yaml"

    def __init__(self, run=True, validate_config=True):
        self.config = self._load_config(validate=validate_config)
        self.wait_events = 0
        super().__init__(self.config.main.required.command_prefix)

        self.game = (
            self.config.main.optional.game
            if self.config.main.optional.get("game")
            else None
        )

        self.plugin_api = PluginAPI(bot=self)
        self.database_api = DatabaseAPI(bot=self)
        self.error_api = ErrorAPI(bot=self)

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
        try:
            self.loop.run_until_complete(super().start(*args, **kwargs))
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.logout())
        finally:
            self.loop.close()

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
            self.validate_config()

        return self.config

    def validate_config(self):
        """Validates several config subsections."""
        for subsection in ["required", "database"]:
            self._validate_config_subsection("main", subsection)
        for subsection in list(self.config.plugins.keys()):
            self._validate_config_subsection("plugins", subsection)

    def _validate_config_subsection(self, section, subsection):
        """Loops through a config subsection to check for missing values.

        section (str): the section name containing the subsection
        subsection (str): the subsection name
        """
        for key, value in self.config.get(section, {}).get(subsection, {}).items():
            error_key = None
            if value is None:
                error_key = key
            elif isinstance(value, dict):
                for k, v in value.items():
                    if v is None:
                        error_key = k
            if error_key:
                if section == "plugins":
                    if not subsection in self.config.main.disabled_plugins:
                        # pylint: disable=line-too-long
                        log.warning(
                            f"Disabling loading of plugin {subsection} due to missing config key {error_key}"
                        )
                        # disable the plugin if we can't get its config
                        self.config.main.disabled_plugins.append(subsection)
                else:
                    raise ValueError(
                        f"Config key {error_key} from {section}.{subsection} not supplied"
                    )

    async def wait_for(self, *args, **kwargs):
        """Wraps the wait_for method to limit the maximum concurrent listeners."""
        if self.wait_events > self.config.main.required.max_waits:
            log.warning("Ignoring wait-for call due to max listeners reached")
            return (None, None, None, None)

        self.wait_events += 1
        response_tuple = await super().wait_for(*args, **kwargs)
        self.wait_events -= 1
        return response_tuple
