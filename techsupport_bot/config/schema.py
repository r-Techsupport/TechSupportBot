from dataclasses import dataclass, field
import discord
from . import RolePermissions

@dataclass
class ConfigSchema:
    admin_factoids_roles: RolePermissions = field(default_factory=RolePermissions)
    """The roles required to administrate factoids."""

    all_assignable_roles: RolePermissions = field(default_factory=RolePermissions)
    """The list of roles by name that moderators can assign to people."""

    allow_duck_manipulation: bool = True
    """Controls whether release, donate, or kill commands are enabled."""

    application_message: str = "Apply now!"
    """The message to show users when they are prompted to apply in the notification channels."""

    automod_max_mentions: int = field(
        default=3,
        metadata={
            "min": 0,
            "max": 10
        }
    )
    """Max number of mentions allowed in a message before triggering auto-protect."""

    reports_channel: discord.abc.Messageable | None = None
    """The channel to send reports to from the /report command"""

