"""Module for defining the plugin bot methods."""

import glob
import inspect
import os

import botlog
import munch
import yaml
from discord.ext import commands


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


class PluginBot(commands.Bot):
    """Parent bot object that supports basic file config and plugins."""

    CONFIG_PATH = "./config.yml"
    PLUGINS_DIR = f"{os.path.join(os.path.dirname(__file__))}/../plugins"
    PluginConfig = PluginConfig

    def __init__(self, prefix=".", intents=None, allowed_mentions=None):
        self.plugins = munch.Munch()
        self.file_config = None
        self.load_file_config()
        super().__init__(
            command_prefix=prefix, intents=intents, allowed_mentions=allowed_mentions
        )

        self.logger = botlog.BotLogger(
            bot=self,
            name=self.__class__.__name__,
            queue_wait=self.file_config.main.logging.queue_wait_seconds,
            send=not self.file_config.main.logging.block_discord_send,
        )

        self.run(self.file_config.main.auth_token)

    def load_file_config(self, validate=True):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH, encoding="utf8") as iostream:
            config_ = yaml.safe_load(iostream)

        self.file_config = munch.munchify(config_)

        self.file_config.main.disabled_plugins = (
            self.file_config.main.disabled_plugins or []
        )

        if not validate:
            return

        for subsection in ["required"]:
            self.validate_bot_config_subsection("main", subsection)

    def validate_bot_config_subsection(self, section, subsection):
        """Loops through a config subsection to check for missing values.

        parameters:
            section (str): the section name containing the subsection
            subsection (str): the subsection name
        """
        for key, value in self.file_config.get(section, {}).get(subsection, {}).items():
            error_key = None
            if value is None:
                error_key = key
            elif isinstance(value, dict):
                for k, v in value.items():
                    if v is None:
                        error_key = k
            if error_key:
                raise ValueError(
                    f"Config key {error_key} from {section}.{subsection} not supplied"
                )

    def get_plugin_modules(self):
        """Gets the current list of plugin modules."""
        self.logger.console.info(f"Searching {self.PLUGINS_DIR} for plugins")
        return [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.PLUGINS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]

    def get_all_plugin_statuses(self):
        """Gets the status of all plugins."""
        self.logger.console.info("Getting plugin status")
        statuses = {}
        for plugin_name in self.get_plugin_modules():
            statuses[plugin_name] = self.get_plugin_status(plugin_name)
        return statuses

    def get_plugin_status(self, plugin_name):
        """Gets the status for a single plugin.

        parameters:
            plugin_name (str): the name of the plugin
        """
        if not plugin_name in self.get_plugin_modules():
            return None

        plugin_data = self.plugins.get(plugin_name, {}).copy()

        if plugin_data:
            status = "loaded"
        elif plugin_name in self.file_config.main.disabled_plugins:
            status = "disabled"
        else:
            status = "unloaded"

        plugin_data["status"] = status

        plugin_data["cogs"] = {
            cog: self.get_cog(cog) for cog in plugin_data.get("cogs", [])
        }

        return munch.munchify(plugin_data)

    def load_plugin(self, plugin_name):
        """Loads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
        """
        self.logger.console.info(f"Loading plugin: {plugin_name}")

        if self.plugins.get(plugin_name):
            message = f"Plugin {plugin_name} already loaded - ignoring load request"
            self.logger.console.warning(message)
            return self._build_plugin_response(False, message)

        if plugin_name in self.file_config.main.disabled_plugins:
            message = f"Plugin {plugin_name} is disabled in bot config - ignoring load request"
            self.logger.console.warning(message)
            return self._build_plugin_response(False, message)

        try:
            self.load_extension(f"plugins.{plugin_name}")
            message = f"Successfully loaded plugin: {plugin_name}"
            self.logger.console.info(message)
            return self._build_plugin_response(True, message)

        except Exception as e:  # pylint: disable=broad-except
            message = f"Unable to load plugin: {plugin_name} (reason: {e})"
            self.logger.console.error(message)
            return self._build_plugin_response(False, message)

    def unload_plugin(self, plugin_name):
        """Unloads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
        """
        self.logger.console.info(f"Unloading plugin: {plugin_name}")

        if not self.plugins.get(plugin_name):
            message = f"Plugin {plugin_name} not loaded - ignoring unload request"
            return self._build_plugin_response(False, message)

        try:
            self.unload_extension(f"plugins.{plugin_name}")
            del self.plugins[plugin_name]
            return self._build_plugin_response(
                True, f"Successfully unloaded plugin: {plugin_name}"
            )

        except Exception as e:  # pylint: disable=broad-except
            message = f"Unable to unload plugin: {plugin_name} (reason: {e})"
            self.logger.console.error(message)
            return self._build_plugin_response(False, message)

    def reload_plugin(self, plugin_name):
        """Reloads a plugin by name.

        parameters:
            plugin_name (str): the name of the plugin file
        """
        self.unload_plugin(plugin_name)
        self.load_plugin(plugin_name)

    def load_all_plugins(self):
        """Loads all plugins currently in the plugins directory."""
        self.logger.console.debug("Retrieving plugin modules")
        for plugin_name in self.get_plugin_modules():
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
                self.logger.console.debug(f"Found plugin module name: {plugin_name}")
                break

        if not plugin_name:
            raise RuntimeError("Could not obtain module name for plugin")

        instanced_cogs = []
        for cog in cogs:
            self.logger.console.debug(f"Adding cog: {cog.__name__}")
            try:
                cog_instance = cog(
                    self,
                    models=models,
                    plugin_name=plugin_name,
                    no_guild=no_guild,
                )
            except TypeError:
                cog_instance = cog(self)

            self.add_cog(cog_instance)
            instanced_cogs.append(cog_instance)

        config = config.data if config else {}

        self.logger.console.debug(f"Registering plugin name: {plugin_name}")
        self.plugins[plugin_name] = munch.munchify(
            {
                "status": "loaded",
                "fallback_config": config,
                "memory": munch.Munch(),
                "cogs": [cog.qualified_name for cog in instanced_cogs],
            }
        )

    @staticmethod
    def _build_plugin_response(status, message):
        """Makes a plugin response object.

        parameters:
            status (bool): True if the status was successful
            message (str): the response message
        """
        return munch.munchify({"status": status, "message": message})
