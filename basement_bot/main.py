"""Basement Bot main thread.
"""

import os

from bot import BasementBot

basementbot = BasementBot(
    command_prefix=os.environ.get("COMMAND_PREFIX", "."),
    debug=bool(int(os.environ.get("DEBUG", 0))),
)

basementbot.run(os.environ.get("AUTH_TOKEN", None))
