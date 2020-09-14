import yaml
import munch

from utils.logger import get_logger

log = get_logger("Config")


class ConfigAPI:

    CONFIG_PATH = "./config.yaml"

    def __init__(self, bot):
        self.bot = bot
        self.config = self._load_config()

    def _load_config(self):
        with open(self.CONFIG_PATH) as iostream:
            config = yaml.safe_load(iostream)
        for key, value in config.get("main", {}).get("required", {}).items():
            if not value:
                raise ValueError(f"Required config {key} not supplied")
        self.config = munch.munchify(config)