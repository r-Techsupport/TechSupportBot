from dataclasses import dataclass, field

import discord

from .role_permissions import RolePermissions


@dataclass
class ConfigSchema:
    allow_duck_manipulation: bool = True
    """Controls whether release, donate, or kill commands are enabled."""

    application_message: str = "Apply now!"
    """The message to show users when they are prompted to apply in the notification channels."""

    automod_max_mentions: int = field(default=3, metadata={"min": 0, "max": 10})
    """Max number of mentions allowed in a message before triggering auto-protect."""

    reports_channel: discord.abc.Messageable = None
    """The channel to send reports to from the /report command"""
