"""This file will hold the core moderation functions. These functions will:
Do the proper moderative action and return true if successful, false if not."""

from datetime import timedelta

import discord
from base import cogs


class ModerationFunctions(cogs.BaseCog):
    async def ban_user(
        self, guild: discord.Guild, user: discord.User, delete_days: int, reason: str
    ) -> bool:
        # Ban the user
        await guild.ban(
            user,
            reason=reason,
            delete_message_days=delete_days,
        )
        return True

    async def unban_user(
        self, guild: discord.Guild, user: discord.User, reason: str
    ) -> bool:
        # Attempt to unban. If the user isn't found, return false
        try:
            await guild.unban(user, reason=reason)
            return True
        except discord.NotFound:
            return False

    async def kick_user(
        self, guild: discord.Guild, user: discord.Member, reason: str
    ) -> bool:
        await guild.kick(user, reason=reason)
        return True

    async def mute_user(
        self, user: discord.Member, reason: str, duration: timedelta
    ) -> bool:
        await user.timeout(until=duration, reason=reason)
        return True

    async def unmute_user(self, user: discord.Member, reason: str) -> bool:
        await user.timeout(reason=reason)

    async def warn_user() -> bool:
        ...

    async def unwarn_user() -> bool:
        ...
