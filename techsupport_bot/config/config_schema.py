from dataclasses import dataclass, field
import discord

@dataclass
class RolePermissions:
    role_id_list: list[int] = field(default_factory=list)
    discord_role_list: list[discord.Role] = field(default_factory=list)

    def check_if_has_permissions(member: discord.Member) -> bool:
        ...
    
    def __str__() -> str:
        ...


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

    automod_max_mentions: int = 3
    """Max number of mentions allowed in a message before triggering auto-protect."""

    reports_channel: discord.abc.Messageable | None = None
    """The channel to send reports to from the /report command"""

class Config(ConfigSchema):
    def load_json():
        ...
    ...

config = Config()

config.reports_channel.send(content="example")
