"""Provides an interface for plugin loading.
"""

import glob
import os

import api
import logger
import munch

log = logger.get_logger("Plugin Loader")


class PluginAPI(api.BotAPI):
    """API for plugin loading."""

    PLUGINS_DIR = f"{os.path.join(os.path.dirname(__file__))}/plugins"

    def __init__(self, bot):
        super().__init__(bot)
        self.plugins = munch.Munch()

    def get_modules(self):
        """Gets the current list of plugin modules."""
        return [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.PLUGINS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]

    def get_status(self):
        """Gets the bot plugin status.

        returns (dict): the set of loaded and available to load plugins
        """
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
        if self.plugins.get(plugin_name):
            message = f"Plugin `{plugin_name}` already loaded - ignoring"
            log.warning(message)
            return self._make_response(False, message)

        if plugin_name in self.bot.config.main.disabled_plugins:
            message = f"Plugin `{plugin_name}` is disabled in bot config - ignoring"
            log.warning(message)
            return self._make_response(False, message)

        try:
            self.bot.load_extension(f"plugins.{plugin_name}")
            self.plugins[plugin_name] = munch.munchify(
                {"status": "loaded", "memory": {}}
            )
            return self._make_response(True, f"Successfully loaded `{plugin_name}`")

        except Exception as e:  # pylint: disable=broad-except
            if allow_failure:
                message = f"Failed to load `{plugin_name}`: `{str(e)}`"
                log.warning(message)
                return self._make_response(False, message)
            raise RuntimeError from e

    def unload_plugin(self, plugin_name, allow_failure=True):
        """Unloads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
            bot (BasementBot): the bot object to which the plugin is loaded
            allow_failure (bool): True if loader does not raise an exception
        """
        if not self.plugins.get(plugin_name):
            message = f"Plugin `{plugin_name}` not loaded - ignoring"
            log.debug(message)
            return self._make_response(False, message)

        try:
            self.bot.unload_extension(f"plugins.{plugin_name}")
            del self.plugins[plugin_name]
            return self._make_response(True, f"Successfully unloaded `{plugin_name}`")

        except Exception as e:  # pylint: disable=broad-except
            if allow_failure:
                message = f"Failed to unload `{plugin_name}`: {str(e)}"
                log.warning(message)
                return self._make_response(False, message)

            raise RuntimeError from e

    def load_plugins(self, allow_failure=True):
        """Loads all plugins currently in the plugins directory.

        parameters:
            bot (BasementBot): the bot object to which the plugin is loaded
            allow_failure (bool): True if loader does not raise an exception
        """
        for plugin_name in self.get_modules():
            log.info(f"Attempting to load plugin module `{plugin_name}`")
            self.load_plugin(plugin_name, allow_failure)

    @staticmethod
    def _make_response(status, message):
        return munch.munchify({"status": status, "message": message})
