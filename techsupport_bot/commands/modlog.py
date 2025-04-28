"""Commands and functions to log and interact with logs of bans and unbans"""

from __future__ import annotations

import datetime
from collections import Counter
from typing import TYPE_CHECKING, Self

import discord
import munch
import ui
from core import auxiliary, cogs, extensionconfig
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="alert_channel",
        datatype="int",
        title="Alert channel ID",
        description="The ID of the channel to send auto-protect alerts to",
        default=None,
    )
    await bot.add_cog(BanLogger(bot=bot, extension_name="modlog"))
    bot.add_extension_config("modlog", config)


class BanLogger(cogs.BaseCog):
    """The class that holds the /modlog commands

    Attributes:
        modlog_group (app_commands.Group): The group for the /modlog commands
    """

    modlog_group = app_commands.Group(
        name="modlog", description="...", extras={"module": "modlog"}
    )

    @modlog_group.command(
        name="highscores",
        description="Shows the top 10 moderators based on ban count",
        extras={"module": "modlog"},
    )
    async def high_score_command(self: Self, interaction: discord.Interaction) -> None:
        """Gets the top 10 moderators based on banned user count

        Args:
            interaction (discord.Interaction): The interaction that started this command
        """
        all_bans = await self.bot.models.BanLog.query.where(
            self.bot.models.BanLog.guild_id == str(interaction.guild.id)
        ).gino.all()
        ban_frequency_counter = Counter(ban.banning_moderator for ban in all_bans)

        sorted_ban_frequency = sorted(
            ban_frequency_counter.items(), key=lambda x: x[1], reverse=True
        )
        embed = discord.Embed(title="Most active moderators")

        final_string = ""
        for index, (moderator_id, count) in enumerate(sorted_ban_frequency):
            moderator = await interaction.guild.fetch_member(int(moderator_id))
            if moderator:
                final_string += (
                    f"{index+1}. {moderator.display_name} "
                    f"{moderator.mention} ({moderator.id}) - ({count})\n"
                )
            else:
                final_string += {f"{index+1}. Moderator left: {moderator_id}"}

        embed.description = final_string
        embed.color = discord.Color.blue()
        await interaction.response.send_message(embed=embed)

    @modlog_group.command(
        name="lookup-user",
        description="Looks up the 10 most recent bans for a given user",
        extras={"module": "modlog"},
    )
    async def lookup_user_command(
        self: Self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """This is the core of the /modlog lookup-user command

        Args:
            interaction (discord.Interaction): The interaction that called the command
            user (discord.User): The user to search for bans for
        """
        recent_bans_by_user = (
            await self.bot.models.BanLog.query.where(
                self.bot.models.BanLog.guild_id == str(interaction.guild.id)
            )
            .where(self.bot.models.BanLog.banned_member == str(user.id))
            .order_by(self.bot.models.BanLog.ban_time.desc())
            .limit(10)
            .gino.all()
        )

        all_bans_by_user = (
            await self.bot.models.BanLog.query.where(
                self.bot.models.BanLog.guild_id == str(interaction.guild.id)
            )
            .where(self.bot.models.BanLog.banned_member == str(user.id))
            .order_by(self.bot.models.BanLog.ban_time.desc())
            .gino.all()
        )

        embeds = []
        for ban in recent_bans_by_user:
            temp_embed = await self.convert_ban_to_pretty_string(
                ban, f"{user.name} bans"
            )
            temp_embed.description += f"\n**Total bans:** {len(all_bans_by_user)}"
            embeds.append(temp_embed)

        if len(embeds) == 0:
            embed = auxiliary.prepare_deny_embed(
                f"No bans for the user {user.name} could be found"
            )
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer(ephemeral=False)
        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)

    @modlog_group.command(
        name="lookup-moderator",
        description="Looks up the 10 most recent bans by a given moderator",
        extras={"module": "modlog"},
    )
    async def lookup_moderator_command(
        self: Self, interaction: discord.Interaction, moderator: discord.Member
    ) -> None:
        """This is the core of the /modlog lookup-moderator command

        Args:
            interaction (discord.Interaction): The interaction that called the command
            moderator (discord.Member): The moderator to search for bans for
        """
        recent_bans_by_user = (
            await self.bot.models.BanLog.query.where(
                self.bot.models.BanLog.guild_id == str(interaction.guild.id)
            )
            .where(self.bot.models.BanLog.banning_moderator == str(moderator.id))
            .order_by(self.bot.models.BanLog.ban_time.desc())
            .limit(10)
            .gino.all()
        )

        all_bans_by_user = (
            await self.bot.models.BanLog.query.where(
                self.bot.models.BanLog.guild_id == str(interaction.guild.id)
            )
            .where(self.bot.models.BanLog.banning_moderator == str(moderator.id))
            .order_by(self.bot.models.BanLog.ban_time.desc())
            .gino.all()
        )

        embeds = []
        for ban in recent_bans_by_user:
            temp_embed = await self.convert_ban_to_pretty_string(
                ban, f"Bans by {moderator.name}"
            )
            temp_embed.description += f"\n**Total bans:** {len(all_bans_by_user)}"
            embeds.append(temp_embed)

        if len(embeds) == 0:
            embed = auxiliary.prepare_deny_embed(
                f"No bans by the user {moderator.name} could be found"
            )
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer(ephemeral=False)
        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)

    async def convert_ban_to_pretty_string(
        self: Self, ban: munch.Munch, title: str
    ) -> discord.Embed:
        """This converts a database ban entry into a shiny embed

        Args:
            ban (munch.Munch): The ban database entry
            title (str): The title to set the embeds to

        Returns:
            discord.Embed: The fancy embed
        """
        member = await self.bot.fetch_user(int(ban.banned_member))
        moderator = await self.bot.fetch_user(int(ban.banning_moderator))
        embed = discord.Embed(title=title)
        embed.description = (
            f"**Case:** {ban.pk}\n"
            f"**Offender:** {member.name} {member.mention}\n"
            f"**Reason:** {ban.reason}\n"
            f"**Responsible moderator:** {moderator.name} {moderator.mention}"
        )
        embed.timestamp = ban.ban_time
        embed.color = discord.Color.red()
        return embed

    @commands.Cog.listener()
    async def on_member_ban(
        self: Self, guild: discord.Guild, user: discord.User | discord.Member
    ) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_ban

        Args:
            guild (discord.Guild): The guild the user got banned from
            user (discord.User | discord.Member): The user that got banned. Can be either User
                or Member depending if the user was in the guild or not at the time of removal.
        """
        await discord.utils.sleep_until(
            discord.utils.utcnow() + datetime.timedelta(seconds=2)
        )

        entry = None
        moderator = None
        async for entry in guild.audit_logs(
            limit=10, action=discord.AuditLogAction.ban
        ):
            if entry.target.id == user.id:
                moderator = entry.user
                break

        if not entry:
            return

        if not moderator or moderator.bot:
            return

        await log_ban(self.bot, user, moderator, guild, entry.reason)

    @commands.Cog.listener()
    async def on_member_unban(
        self: Self, guild: discord.Guild, user: discord.User
    ) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_unban

        Args:
            guild (discord.Guild): The guild the user got unbanned from
            user (discord.User): The user that got unbanned
        """
        # Wait a short time to ensure the audit log has been updated
        await discord.utils.sleep_until(
            discord.utils.utcnow() + datetime.timedelta(seconds=2)
        )

        entry = None
        moderator = None
        async for entry in guild.audit_logs(
            limit=10, action=discord.AuditLogAction.unban
        ):
            if entry.target.id == user.id:
                moderator = entry.user
        if not entry:
            return

        if not moderator or moderator.bot:
            return

        await log_unban(self.bot, user, moderator, guild, entry.reason)


# Any bans initiated by TS will come through this
async def log_ban(
    bot: bot.TechSupportBot,
    banned_member: discord.User | discord.Member,
    banning_moderator: discord.Member,
    guild: discord.Guild,
    reason: str,
) -> None:
    """Logs a ban into the alert channel

    Args:
        bot (bot.TechSupportBot): The bot object to use for the logging
        banned_member (discord.User | discord.Member): The member who was banned
        banning_moderator (discord.Member): The moderator who banned the member
        guild (discord.Guild): The guild the member was banned from
        reason (str): The reason for the ban
    """
    config = bot.guild_configs[str(guild.id)]
    if "modlog" not in config.get("enabled_extensions", []):
        return

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
            int(config.extensions.modlog.alert_channel.value)
        )
    except TypeError:
        alert_channel = None

    if not alert_channel:
        return

    await alert_channel.send(embed=embed)


async def log_unban(
    bot: bot.TechSupportBot,
    unbanned_member: discord.User | discord.Member,
    unbanning_moderator: discord.Member,
    guild: discord.Guild,
    reason: str,
) -> None:
    """Logs an unban into the alert channel

    Args:
        bot (bot.TechSupportBot): The bot object to use for the logging
        unbanned_member (discord.User | discord.Member): The member who was unbanned
        unbanning_moderator (discord.Member): The moderator who unbanned the member
        guild (discord.Guild): The guild the member was unbanned from
        reason (str): The reason for the unban
    """
    config = bot.guild_configs[str(guild.id)]
    if "modlog" not in config.get("enabled_extensions", []):
        return

    if not reason:
        reason = "No reason specified"

    embed = discord.Embed(title="unban")
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
            int(config.extensions.modlog.alert_channel.value)
        )
    except TypeError:
        alert_channel = None

    if not alert_channel:
        return

    await alert_channel.send(embed=embed)
