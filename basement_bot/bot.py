"""Module for the main bot object.
"""

import logging

from discord.ext.commands import Bot

from plugin import PluginLoader


class BasementBot(Bot):
    """Defines initialization and event handlers.

    parameters:
        command_prefix (str): the prefix for commands
        debug (bool): True if debug mode enabled
    """

    def __init__(self, command_prefix, debug):
        self.command_prefix = command_prefix
        self.debug = debug
        super().__init__(command_prefix)

        self._set_logging()

        self.plugin_loader = PluginLoader(self)
        self.plugin_loader.load_plugins()

    async def on_ready(self):
        """Logs startup success. Runs after initialization is complete.
        """
        logging.info(f"Initialization complete")
        logging.info(f"Commands available with the `{self.command_prefix}` prefix")

    async def on_error(self, event, *args, **kwargs):
        """Logs any errors handled on an event.
            
        parameters:
            event (discord.Event): the event on which the error is handled
        """
        error = f"Error when running {event}: {args}, {kwargs}"
        logging.error(error)

    def _set_logging(self):
        """Sets logging level.
        """
        logging.getLogger().setLevel(logging.DEBUG if self.debug else logging.INFO)
        logging.debug("Debug logging enabled")
