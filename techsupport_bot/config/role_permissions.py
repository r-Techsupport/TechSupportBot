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
