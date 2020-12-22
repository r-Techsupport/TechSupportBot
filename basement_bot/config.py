"""Provides an interface for loading, validating, and changing the config.
"""
import munch
import yaml
from api import BotAPI
from utils.logger import get_logger

log = get_logger("Config")


class ConfigAPI(BotAPI):
    """API for handling errors.

    parameters:
        bot (BasementBot): the bot object
        validate_config (bool): True if the bot's config should be validated
    """

    CONFIG_PATH = "./config.yaml"

    def __init__(self, bot, validate):
        super().__init__(bot)
        self.bot.config = self.load_config(validate)

    def load_config(self, validate):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH) as iostream:
            config = yaml.safe_load(iostream)
        self.config = munch.munchify(config)

        self.config.main.disabled_plugins = self.config.main.disabled_plugins or []

        if validate:
            self.validate_config()

        return self.config

    def validate_config(self):
        """Validates several config subsections."""
        for subsection in ["required", "database"]:
            self.validate_config_subsection("main", subsection)
        for subsection in list(self.config.plugins.keys()):
            self.validate_config_subsection("plugins", subsection)

    def validate_config_subsection(self, section, subsection):
        """Loops through a config subsection to check for missing values.
        
        parameters:
            section (str): the section name containing the subsection
            subsection (str): the subsection name
        """
        for key, value in self.config.get(section, {}).get(subsection, {}).items():
            error_key = None
            if value is None:
                error_key = key
            elif isinstance(value, dict):
                for k, v in value.items():
                    if v is None:
                        error_key = k
            if error_key:
                if section == "plugins":
                    if not subsection in self.config.main.disabled_plugins:
                        # pylint: disable=line-too-long
                        log.warning(
                            f"Disabling loading of plugin {subsection} due to missing config key {error_key}"
                        )
                        # disable the plugin if we can't get its config
                        self.config.main.disabled_plugins.append(subsection)
                else:
                    raise ValueError(
                        f"Config key {error_key} from {section}.{subsection} not supplied"
                    )
