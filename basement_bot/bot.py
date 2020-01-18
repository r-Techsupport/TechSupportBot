"""The BasementBot client library
"""

import logging
from os.path import dirname, basename, isfile, join
import importlib
import glob

from exceptions import BotException

from discord.ext.commands import Bot

class BasementBot(Bot):

    def __init__(self, server_name, command_prefix, debug):
        self.server_name = server_name
        self.command_prefix = command_prefix
        self.debug = debug
        super().__init__(command_prefix)

        self._set_logging()
        self._load_plugins()

    async def on_ready(self):
        logging.info(f"BasementBot successfully started on server {self.server_name}")
        logging.info(f"Commands available with the `{self.command_prefix}` prefix")

    async def on_error(self, event, *args, **kwargs):
        error = f"Error when running {event}: {args}"
        logging.error(error)

    def _set_logging(self):
        logging.getLogger().setLevel(
            logging.DEBUG if self.debug else logging.INFO
        )
        logging.debug("Debug logging enabled")

    def _load_plugins(self):
        wildcard = f"{join(dirname(__file__))}/plugins/*.py"
        files = glob.glob(wildcard)
        module_names = [ 
            f"plugins.{basename(f)[:-3]}" for f in files if isfile(f) and not f.endswith('__init__.py')
        ]
        for module in module_names:
            imported = importlib.import_module(module)
            for name, func in imported.__dict__.items():
                if not name.startswith("__") and name != "commands":
                    logging.info(f"Loading command `{name}` from module {module}")
                    self.add_command(func)
