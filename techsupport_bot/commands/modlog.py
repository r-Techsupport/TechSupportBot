from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
from core import cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(BanLogger(bot=bot, extension_name="modlog"))


class BanLogger(cogs.BaseCog):
    async def high_score_command(self: Self, interaction: discord.Interaction): ...

    async def lookup_user_command(
        self: Self, interaction: discord.Interaction, user: discord.User
    ): ...

    async def lookup_moderator_command(
        self: Self, interaction: discord.Interaction, moderator: discord.Member
    ): ...

    @commands.Cog.listener()
    async def on_member_ban(
        self: Self, guild: discord.Guild, user: discord.User | discord.Member
    ) -> None:
        await discord.utils.sleep_until(
            discord.utils.utcnow() + datetime.timedelta(seconds=2)
        )

        # Fetch the audit logs for the ban action
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if entry.target.id == user.id:
                moderator = entry.user

        if moderator.bot:
            return

        await log_ban(self.bot, user, moderator, guild, entry.reason)

    @commands.Cog.listener()
    async def on_member_unban(
        self: Self, guild: discord.Guild, user: discord.User
    ) -> None:
        # Wait a short time to ensure the audit log has been updated
        await discord.utils.sleep_until(
            discord.utils.utcnow() + datetime.timedelta(seconds=2)
        )

        # Fetch the audit logs for the unban action
        async for entry in guild.audit_logs(
            limit=1, action=discord.AuditLogAction.unban
        ):
            if entry.target.id == user.id:
                moderator = entry.user

        if moderator.bot:
            return

        await log_unban(self.bot, user, moderator, guild, entry.reason)


# Any bans initiated by TS will come through this
async def log_ban(
    bot: bot.TechSupportBot,
    banned_member: discord.User | discord.Member,
    banning_moderator: discord.Member,
    guild: discord.Guild,
    reason: str,
):
    if not reason:
        reason = "No reason specified"

    ban = bot.models.BanLog(
        guild_id=str(guild.id),
        reason=reason,
        banning_moderator=str(banning_moderator.id),
        banned_member=str(banned_member.id),
    )
    ban = await ban.create()

    embed = discord.Embed(title=f"ban | case {ban.pk}")
    embed.description = (
        f"**Offender:** {banned_member.name} {banned_member.mention}\n"
        f"**Reason:** {reason}\n"
        f"**Responsible moderator:** {banning_moderator.name} {banning_moderator.mention}"
    )
    embed.set_footer(text=f"ID: {banned_member.id}")
    embed.timestamp = datetime.datetime.utcnow()
    embed.color = discord.Color.red()

    config = bot.guild_configs[str(guild.id)]

    try:
        alert_channel = guild.get_channel(
            int(config.extensions.protect.alert_channel.value)
        )
    except TypeError:
        alert_channel = None

    if not alert_channel:
        return

    await alert_channel.send(embed=embed)


async def log_unban(
    unbanned_member: discord.User | discord.Member,
    unbanning_moderator: discord.Member,
    guild: discord.Guild,
    reason: str,
):
    if not reason:
        reason = "No reason specified"

    embed = discord.Embed(title=f"unban")
    embed.description = (
        f"**Offender:** {unbanned_member.name} {unbanned_member.mention}\n"
        f"**Reason:** {reason}\n"
        f"**Responsible moderator:** {unbanning_moderator.name} {unbanning_moderator.mention}"
    )
    embed.set_footer(text=f"ID: {unbanned_member.id}")
    embed.timestamp = datetime.datetime.utcnow()
    embed.color = discord.Color.green()

    config = bot.guild_configs[str(guild.id)]

    try:
        alert_channel = guild.get_channel(
            int(config.extensions.protect.alert_channel.value)
        )
    except TypeError:
        alert_channel = None

    if not alert_channel:
        return

    await alert_channel.send(embed=embed)
