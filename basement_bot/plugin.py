"""Provides an interface for plugin loading.
"""

import glob
import importlib
import os
import sys

import munch
from discord.ext import commands


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

        # pylint: disable=broad-except
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
            self.plugins[plugin_name] = self.load_extension(f"plugins.{plugin_name}")

            message = f"Successfully loaded plugin: {plugin_name}"
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
            return self._make_response(
                True, f"Successfully unloaded plugin: {plugin_name}"
            )

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
            self.load_plugin(plugin_name, allow_failure=allow_failure)

    def process_plugin_setup(self, cogs, models=None, config=None):
        """Loads a set of cogs and other objects representing a single plugin.

        parameters:
            cogs (List[discord.ext.Cog]): the list of cogs to load
            config (PluginConfig): the plugin config
            models (List[gino.Model]): the Postgres models for the plugin
        """
        for cog in cogs:
            self.bot.add_cog(cog(self.bot, models=models))

        config = config.data if config else {}

        return munch.munchify(
            {"status": "loaded", "config": config, "memory": munch.Munch()}
        )

    def load_extension(self, name):
        """Copies the discord.py load_extension logic.

        This is done so `return ...` can be utilized in the setup function.

        parameters:
            name (str): the name of the extension to load
        """
        # pylint: disable=protected-access
        if name in self.bot._BotBase__extensions:
            raise commands.errors.ExtensionAlreadyLoaded(name)

        spec = importlib.util.find_spec(name)
        if spec is None:
            raise commands.errors.ExtensionNotFound(name)

        # precondition: key not in self.__extensions
        lib = importlib.util.module_from_spec(spec)
        sys.modules[name] = lib
        try:
            spec.loader.exec_module(lib)
        except Exception as e:
            del sys.modules[name]
            raise commands.errors.ExtensionFailed(name, e) from e

        try:
            setup = getattr(lib, "setup")
        except AttributeError:
            del sys.modules[name]
            # pylint: disable=raise-missing-from
            raise commands.errors.NoEntryPointError(name)

        try:
            # the only part that's different
            plugin_data = setup(self.bot)
            self.bot._BotBase__extensions[name] = lib
            return plugin_data

        except Exception as e:
            del sys.modules[name]
            self.bot._remove_module_references(lib.__name__)
            self.bot._call_module_finalizers(lib, name)
            raise commands.errors.ExtensionFailed(name, e) from e

    @staticmethod
    def _make_response(status, message):
        return munch.munchify({"status": status, "message": message})


class PluginConfig:
    """Represents the config of a plugin."""

    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.data = munch.Munch()

    # pylint: disable=too-many-arguments
    def add(self, key, datatype, title, description, default):
        """Adds a new entry to the config.

        This is usually used in the plugin's setup function.

        parameters:
            key (str): the lookup key for the entry
            datatype (str): the datatype metadata for the entry
            title (str): the title of the entry
            description (str): the description of the entry
            default (Any): the default value to use for the entry
        """
        self.data[key] = {
            "datatype": datatype,
            "title": title,
            "description": description,
            "default": default,
            "value": default,
        }
