"""This file will hold the core moderation functions. These functions will:
Do the proper moderative action and return true if successful, false if not."""

from datetime import timedelta

import discord


class ModerationFunctions:
    def __init__(self, bot):
        self.bot = bot

    async def ban_user(
        self, guild: discord.Guild, user: discord.User, delete_days: int, reason: str
    ) -> bool:
        """A very simple function that bans a given user from the passed guild

        Args:
            guild (discord.Guild): The guild to ban from
            user (discord.User): The user who needs to be banned
            delete_days (int): The numbers of days of past messages to delete
            reason (str): The reason for banning

        Returns:
            bool: True if ban was successful
        """
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
        """A very simple functon that unbans a given user from the passed guild

        Args:
            guild (discord.Guild): The guild to unban from
            user (discord.User): The user to unban
            reason (str): The reason they are being unbanned

        Returns:
            bool: True if unban was successful
        """
        # Attempt to unban. If the user isn't found, return false
        try:
            await guild.unban(user, reason=reason)
            return True
        except discord.NotFound:
            return False

    async def kick_user(
        self, guild: discord.Guild, user: discord.Member, reason: str
    ) -> bool:
        """A very simple function that kicks a given user from the guild

        Args:
            guild (discord.Guild): The guild to kick from
            user (discord.Member): The member to kick from the guild
            reason (str): The reason they are being kicked

        Returns:
            bool: True if kick was successful
        """
        await guild.kick(user, reason=reason)
        return True

    async def mute_user(
        self, user: discord.Member, reason: str, duration: timedelta
    ) -> bool:
        """Times out a given user

        Args:
            user (discord.Member): The user to timeout
            reason (str): The reason they are being timed out
            duration (timedelta): How long to timeout the user for

        Returns:
            bool: True if the timeout was successful
        """
        await user.timeout(duration, reason=reason)
        return True

    async def unmute_user(self, user: discord.Member, reason: str) -> bool:
        """Untimes out a given user.

        Args:
            user (discord.Member): The user to untimeout
            reason (str): The reason they are being untimeout

        Returns:
            bool: True if untimeout was successful
        """
        if not user.timed_out_until:
            return False
        await user.timeout(None, reason=reason)
        return True

    async def warn_user(
        self, user: discord.Member, invoker: discord.Member, reason: str
    ) -> bool:
        await self.bot.models.Warning(
            user_id=str(user.id),
            guild_id=str(invoker.guild.id),
            reason=reason,
            invoker_id=str(invoker.id),
        ).create()
        return True

    async def unwarn_user(self, user: discord.Member, warning: str) -> bool:
        query = (
            self.bot.models.Warning.query.where(
                self.bot.models.Warning.guild_id == str(user.guild.id)
            )
            .where(self.bot.models.Warning.reason == warning)
            .where(self.bot.models.Warning.user_id == str(user.id))
        )
        entry = await query.gino.first()
        if not entry:
            return False
        await entry.delete()
        return True
