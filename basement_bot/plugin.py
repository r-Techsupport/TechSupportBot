"""Provides an interface for plugin loading.
"""

import glob
import inspect
import os

import munch


class PluginAPI:
    """API for plugin loading."""

    PLUGINS_DIR = f"{os.path.join(os.path.dirname(__file__))}/plugins"

    def __init__(self, bot):
        self.bot = bot
        self.plugins = munch.Munch()

    def get_modules(self):
        """Gets the current list of plugin modules."""
        self.bot.logger.console.info(f"Searching {self.PLUGINS_DIR} for plugins")

        return [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.PLUGINS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]

    def get_all_statuses(self):
        """Gets the status of all plugins."""
        self.bot.logger.console.info("Getting plugin status")

        statuses = {}
        for plugin_name in self.get_modules():
            statuses[plugin_name] = self.get_status(plugin_name)

        return statuses

    def get_status(self, plugin_name):
        """Gets the status for a single plugin.

        parameters:
            plugin_name (str): the name of the plugin
        """
        if not plugin_name in self.get_modules():
            return None

        plugin_data = self.plugins.get(plugin_name, {}).copy()

        if plugin_data:
            status = "loaded"
        elif plugin_name in self.bot.config.main.disabled_plugins:
            status = "disabled"
        else:
            status = "unloaded"

        plugin_data["status"] = status

        plugin_data["cogs"] = {
            cog: self.bot.preserialize_object(self.bot.get_cog(cog))
            for cog in plugin_data.get("cogs", [])
        }

        return plugin_data

    def load_plugin(self, plugin_name):
        """Loads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
        """
        self.bot.logger.console.info(f"Loading plugin: {plugin_name}")

        if self.plugins.get(plugin_name):
            message = f"Plugin {plugin_name} already loaded - ignoring load request"
            self.bot.logger.console.warning(message)
            return self._make_response(False, message)

        if plugin_name in self.bot.config.main.disabled_plugins:
            message = f"Plugin {plugin_name} is disabled in bot config - ignoring load request"
            self.bot.logger.console.warning(message)
            return self._make_response(False, message)

        try:
            self.bot.load_extension(f"plugins.{plugin_name}")
            message = f"Successfully loaded plugin: {plugin_name}"
            self.bot.logger.console.info(message)
            return self._make_response(True, message)

        except Exception as e:  # pylint: disable=broad-except
            message = f"Unable to load plugin: {plugin_name} (reason: {e})"
            self.bot.logger.console.error(message)
            return self._make_response(False, message)

    def unload_plugin(self, plugin_name):
        """Unloads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
        """
        self.bot.logger.console.info(f"Unloading plugin: {plugin_name}")

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
            self.bot.logger.console.error(message)
            return self._make_response(False, message)

    def load_plugins(self):
        """Loads all plugins currently in the plugins directory."""
        self.bot.logger.console.debug("Retrieving plugin modules")
        for plugin_name in self.get_modules():
            self.load_plugin(plugin_name)

    def process_plugin_setup(self, cogs, models=None, config=None, no_guild=False):
        """Loads a set of cogs and other objects representing a single plugin.

        parameters:
            cogs (List[discord.ext.Cog]): the list of cogs to load
            config (PluginConfig): the plugin config
            models (List[gino.Model]): the Postgres models for the plugin
            no_guild (bool): True if the plugin should run globally
        """
        plugin_name = None
        for frame in inspect.stack():
            module = inspect.getmodule(frame[0])
            if module.__name__.startswith("plugins."):
                plugin_name = module.__name__.split(".")[-1]
                self.bot.logger.console.debug(
                    f"Found plugin module name: {plugin_name}"
                )
                break

        if not plugin_name:
            raise RuntimeError("Could not obtain module name for plugin")

        instanced_cogs = []
        for cog in cogs:
            self.bot.logger.console.debug(f"Adding cog: {cog.__name__}")
            try:
                cog_instance = cog(
                    self.bot,
                    models=models,
                    plugin_name=plugin_name,
                    no_guild=no_guild,
                )
            except TypeError:
                cog_instance = cog(self.bot)

            self.bot.add_cog(cog_instance)
            instanced_cogs.append(cog_instance)

        config = config.data if config else {}

        self.bot.logger.console.debug(f"Registering plugin name: {plugin_name}")
        self.plugins[plugin_name] = munch.munchify(
            {
                "status": "loaded",
                "fallback_config": config,
                "memory": munch.Munch(),
                "cogs": [cog.qualified_name for cog in instanced_cogs],
            }
        )

    @staticmethod
    def _make_response(status, message):
        """Makes a plugin API response object.

        parameters:
            status (bool): True if the status was successful
            message (str): the response message
        """
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
