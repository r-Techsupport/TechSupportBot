"""Module for plugin loading.
"""

import glob
from os.path import basename, dirname, isfile, join

from utils.logger import get_logger

log = get_logger("Plugin Loader")


class PluginAPI:
    """API for plugin loading.

    parameters:
        bot (BasementBot): the bot object to which plugins are loading
    """

    PLUGINS_DIR = f"{join(dirname(__file__))}/plugins"

    def __init__(self):
        self.plugins = {}

    def get_modules(self):
        """Gets the current list of plugin modules.
        """
        return [
            basename(f)[:-3]
            for f in glob.glob(f"{self.PLUGINS_DIR}/*.py")
            if isfile(f) and not f.endswith("__init__.py")
        ] or None

    def get_status(self):
        """Gets the bot plugin status.

        returns (dict): the set of loaded and available to load plugins
        """
        try:
            return {
                "loaded": [key for key, _ in self.plugins.items()],
                "available": [
                    plugin
                    for plugin in self.get_modules()
                    if not self.plugins.get(plugin)
                ],
            }
        except Exception as e:
            return {"error": str(e)}

    def load_plugin(self, plugin_name, bot, allow_failure=True):
        """Loads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
            bot (Bot): the bot object to which the plugin is loaded
            allow_failure (bool): True if loader does not raise an exception
        """
        if self.plugins.get(plugin_name):
            log.debug(f"Plugin {plugin_name} already loaded - ignoring")
            return

        try:
            bot.load_extension(f"plugins.{plugin_name}")
            self.plugins[plugin_name] = {"status": "loaded"}

        except Exception as e:  # pylint: disable=broad-except
            if allow_failure:
                log.exception(f"Failed to load {plugin_name}: {str(e)}")
            else:
                raise RuntimeError(str(e))

    def load_plugins(self, bot, allow_failure=True):
        """Loads all plugins currently in the plugins directory.

        parameters:
            bot (Bot): the bot object to which the plugin is loaded
            allow_failure (bool): True if loader does not raise an exception
        """
        for plugin_name in self.get_modules():
            log.info(f"Loading plugin module {plugin_name}")
            self.load_plugin(plugin_name, bot, allow_failure)
