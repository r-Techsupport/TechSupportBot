"""Provides an interface for plugin loading.
"""

import glob
import os

import munch


class PluginAPI:
    """API for plugin loading."""

    PLUGINS_DIR = f"{os.path.join(os.path.dirname(__file__))}/plugins"

    def __init__(self, bot):
        self.bot = bot
        self.plugins = munch.Munch()
        self.logger = self.bot.get_logger(self.__class__.__name__)

    def get_modules(self):
        """Gets the current list of plugin modules."""
        self.logger.console.info(f"Searching {self.PLUGINS_DIR} for plugins")

        return [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.PLUGINS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]

    def get_status(self):
        """Gets the bot plugin status.

        returns (dict): the set of loaded and available to load plugins
        """
        self.logger.console.info("Getting plugin status")

        statuses = {}
        
        try:
            for plugin_name in self.get_modules():
                status = "loaded" if self.plugins.get(plugin_name) else "unloaded"
                if (
                    status == "unloaded"
                    and plugin_name in self.bot.config.main.disabled_plugins
                ):
                    status = "disabled"
                statuses[plugin_name] = status

            return statuses

        except Exception as e:
            return {"error": str(e)}

    def load_plugin(self, plugin_name, allow_failure=True):
        """Loads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
            bot (BasementBot): the bot object to which the plugin is loaded
            allow_failure (bool): True if loader does not raise an exception
        """
        self.logger.console.info(f"Loading plugin: {plugin_name}")

        if self.plugins.get(plugin_name):
            message = f"Plugin {plugin_name} already loaded - ignoring load request"
            self.logger.console.warning(message)
            return self._make_response(False, message)

        if plugin_name in self.bot.config.main.disabled_plugins:
            message = f"Plugin {plugin_name} is disabled in bot config - ignoring load request"
            self.logger.console.warning(message)
            return self._make_response(False, message)

        try:
            self.bot.load_extension(f"plugins.{plugin_name}")

            self.plugins[plugin_name] = munch.munchify(
                {"status": "loaded", "memory": {}}
            )

            message =  f"Successfully loaded plugin: {plugin_name}"
            self.logger.console.info(message)
            return self._make_response(True, message)

        except Exception as e:  # pylint: disable=broad-except
            message = f"Unable to load plugin: {plugin_name} (reason: {e})"
            self.logger.console.error(message)
            if allow_failure:
                return self._make_response(False, message)

            raise RuntimeError from e

    def unload_plugin(self, plugin_name, allow_failure=True):
        """Unloads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
            bot (BasementBot): the bot object to which the plugin is loaded
            allow_failure (bool): True if loader does not raise an exception
        """
        self.logger.console.info(f"Unloading plugin: {plugin_name}")

        if not self.plugins.get(plugin_name):
            message = f"Plugin {plugin_name} not loaded - ignoring unload request"
            return self._make_response(False, message)

        try:
            self.bot.unload_extension(f"plugins.{plugin_name}")
            del self.plugins[plugin_name]
            return self._make_response(True, f"Successfully unloaded plugin: {plugin_name}")

        except Exception as e:  # pylint: disable=broad-except
            message = f"Unable to unload plugin: {plugin_name} (reason: {e})"
            self.logger.console.error(message)
            if allow_failure:
                return self._make_response(False, message)
            raise RuntimeError from e

    def load_plugins(self, allow_failure=True):
        """Loads all plugins currently in the plugins directory.

        parameters:
            bot (BasementBot): the bot object to which the plugin is loaded
            allow_failure (bool): True if loader does not raise an exception
        """
        self.logger.console.debug("Retrieving plugin modules")
        for plugin_name in self.get_modules():
            self.load_plugin(plugin_name, allow_failure)

    @staticmethod
    def _make_response(status, message):
        return munch.munchify({"status": status, "message": message})
