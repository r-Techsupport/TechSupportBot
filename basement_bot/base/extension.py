"""Module for defining the extensions bot methods."""

import glob
import os

import botlog
import munch
import yaml
from discord.ext import commands


class ExtensionConfig:
    """Represents the config of an extension."""

    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.data = munch.Munch()

    # pylint: disable=too-many-arguments
    def add(self, key, datatype, title, description, default):
        """Adds a new entry to the config.

        This is usually used in the extensions's setup function.

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


class ExtensionsBot(commands.Bot):
    """Parent bot object that supports basic file config."""

    CONFIG_PATH = "./config.yml"
    EXTENSIONS_DIR_NAME = "extensions"
    EXTENSIONS_DIR = (
        f"{os.path.join(os.path.dirname(__file__))}/../{EXTENSIONS_DIR_NAME}"
    )
    ExtensionConfig = ExtensionConfig

    def __init__(self, prefix=".", intents=None, allowed_mentions=None):
        self.extension_configs = munch.Munch()
        self.extension_states = munch.Munch()
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

        self.file_config.main.disabled_extensions = (
            self.file_config.main.disabled_extensions or []
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

    def get_potential_extensions(self):
        """Gets the current list of extensions in the defined directory."""
        self.logger.console.info(f"Searching {self.EXTENSIONS_DIR} for extensions")
        return [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.EXTENSIONS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]

    def load_extensions(self, graceful=True):
        """Loads all extensions currently in the extensions directory.

        parameters:
            graceful (bool): True if extensions should gracefully fail to load
        """
        self.logger.console.debug("Retrieving extensions")
        for extension_name in self.get_potential_extensions():
            if extension_name in self.file_config.main.disabled_extensions:
                self.logger.console.debug(
                    f"{extension_name} is disabled on startup - ignoring load"
                )
                continue

            try:
                self.load_extension(f"{self.EXTENSIONS_DIR_NAME}.{extension_name}")
            except Exception as exception:
                self.logger.console.error(
                    f"Failed to load extension {extension_name}: {exception}"
                )
                if not graceful:
                    raise exception

    def add_extension_config(self, extension_name, config):
        """Adds a base config object for a given extension.

        parameters:
            extension_name (str): the name of the extension
            config (ExtensionConfig): the extension config object
        """
        if not isinstance(config, self.ExtensionConfig):
            raise ValueError("config must be of type ExtensionConfig")
        self.extension_configs[extension_name] = config

    def get_command_extension_name(self, command):
        """Gets the subname of an extension from a command.

        parameters:
            command (discord.ext.commands.Command): the command to reference
        """
        if not command.module.startswith(f"{self.EXTENSIONS_DIR_NAME}."):
            return None
        extension_name = command.module.split(".")[1]
        return extension_name
