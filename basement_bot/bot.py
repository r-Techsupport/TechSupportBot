"""The BasementBot client library
"""

import logging

from plugin import PluginLoader

from discord.ext.commands import Bot


class BasementBot(Bot):
    """
    """

    def __init__(self, command_prefix, debug):
        self.command_prefix = command_prefix
        self.debug = debug
        super().__init__(command_prefix)

        self._set_logging()

        self.plugin_loader = PluginLoader(self)
        self.plugin_loader.load_plugins()

    async def on_ready(self):
        logging.info(f"Initialization complete")
        logging.info(f"Commands available with the `{self.command_prefix}` prefix")

    async def on_error(self, event, *args, **kwargs):
        error = f"Error when running {event}: {args}, {kwargs}"
        logging.error(error)

    def _set_logging(self):
        logging.getLogger().setLevel(
            logging.DEBUG if self.debug else logging.INFO
        )
        logging.debug("Debug logging enabled")