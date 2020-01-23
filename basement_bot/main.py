"""Basement Bot main thread.
"""

import os

from bot import BasementBot

basementbot = BasementBot(
    command_prefix=os.environ.get("COMMAND_PREFIX", "."), game=os.environ.get("GAME"),
)

basementbot.run(os.environ.get("AUTH_TOKEN", None))
