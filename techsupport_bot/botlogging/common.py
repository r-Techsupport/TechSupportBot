"""A few common functions to help the logging system work smoothly"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import discord


class LogLevel(Enum):
    """This is a way to map log levels to strings, and have the easy ability
    to dynamically add or remove log levels"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class LogContext:
    """A very simple class to store a few contextual items about the log
    This is used to determine if some guild settings means the log shouldn't be logged

    parameters:
        guild (discord.Guild): The guild the log occured with. Optional
        channel (discord.abc.Messageble): The channel, DM, thread,
            or other messagable the log occured in
    """

    guild: Optional[discord.Guild] = None
    channel: Optional[discord.abc.Messageable] = None
