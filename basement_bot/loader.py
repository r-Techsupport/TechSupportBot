"""Module for plugin loading.
"""

import glob
from os.path import basename, dirname, isfile, join

from logger import get_logger

log = get_logger("Plugin Loader")


class PluginLoader:
    """Wrapper for plugin loading.

    parameters:
        bot (BasementBot): the bot object to which plugins are loading
    """

    # pylint: disable=too-few-public-methods
    def __init__(self, bot):
        self.bot = bot

    def load_plugins(self):
        """Adds functions as commands from the plugins directory.
        """
        for plugin in self._get_modules():
            log.info(f"Loading plugin module {plugin}")

            try:
                self.bot.load_extension(plugin)

            except Exception as e:  # pylint: disable=broad-except
                log.exception(f"Failed to load {plugin}: {str(e)}")

    @staticmethod
    def _get_modules():
        """Gets the list of plugin modules.
        """
        files = glob.glob(f"{join(dirname(__file__))}/plugins/*.py")
        return [
            f"plugins.{basename(f)[:-3]}"
            for f in files
            if isfile(f) and not f.endswith("__init__.py")
        ]
