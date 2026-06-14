"""Commands and functions to log and interact with logs of bans and unbans"""

from __future__ import annotations

import asyncio
import datetime
from collections import Counter
from typing import TYPE_CHECKING, Self

import asyncpg
import discord
import munch
from discord import app_commands
from discord.ext import commands

import configuration
import ui
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(ModLogger(bot=bot))


class ModLogger(cogs.BaseCog):
    """The class that holds the /modlog commands

    Attributes:
        modlog_group (app_commands.Group): The group for the /modlog commands
    """

    modlog_group: app_commands.Group = app_commands.Group(
        name="modlog",
        description="Commands that query the database related to mod logs",
    )

    @modlog_group.command(
        name="highscores",
        description="Shows the top 10 moderators based on mod action count",
    )
    async def high_score_command(self: Self, interaction: discord.Interaction) -> None:
        """Gets the top 10 moderators based on mod action count

        Args:
            interaction (discord.Interaction): The interaction that started this command
        """
        await interaction.response.defer()
        all_actions = await self.bot.models.ModLog.query.where(
            self.bot.models.ModLog.guild_id == str(interaction.guild.id)
        ).gino.all()
        frequency_counter = Counter(
            action.moderator_id
            for action in all_actions
            if action.moderator_id is not None
        )

        sorted_frequency = sorted(
            frequency_counter.items(), key=lambda x: x[1], reverse=True
        )
        embed = discord.Embed(title="Most active moderators")

        final_string = ""
        for index, (moderator_id, count) in enumerate(sorted_frequency[:10]):
            try:
                moderator = await interaction.guild.fetch_member(int(moderator_id))
            except discord.NotFound:
                moderator = None
            if moderator:
                final_string += (
                    f"{index + 1}. {moderator.display_name} "
                    f"{moderator.mention} ({moderator.id}) - {count}\n"
                )
            else:
                final_string += (
                    f"{index + 1}. Moderator left: {moderator_id} - {count}\n"
                )

        embed.description = final_string
        embed.color = discord.Color.blue()
        await interaction.followup.send(embed=embed)

    @modlog_group.command(
        name="lookup-user",
        description="Looks up mod actions taken against a given user",
        extras={"ephemeral_error": True},
    )
    async def lookup_user_command(
        self: Self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """This is the core of the /modlog lookup-user command

        Args:
            interaction (discord.Interaction): The interaction that called the command
            user (discord.User): The user to search for bans for
        """
        await interaction.response.defer(ephemeral=True)

        all_action_for_user = (
            await self.bot.models.ModLog.query.where(
                self.bot.models.ModLog.guild_id == str(interaction.guild.id)
            )
            .where(self.bot.models.ModLog.member_id == str(user.id))
            .order_by(self.bot.models.ModLog.action_time.desc())
            .gino.all()
        )

        embeds = []
        embed = discord.Embed(title=f"Actions for {user.name}")
        embed.color = discord.Color.red()
        for index, action in enumerate(all_action_for_user):
            if index % 10 == 0 and index > 0:
                embeds.append(embed)
                embed = discord.Embed(title=f"Actions for {user.name}")
                embed.color = discord.Color.red()
            embed.add_field(
                name=f"Case {action.guild_case_id} | {action.action.title()}",
                value=(
                    f"Reason: {action.reason if action.reason else "No reason specified"}\n"
                    f"<t:{int(action.action_time.timestamp())}>"
                ),
                inline=False,
            )
        embeds.append(embed)

        if len(embeds) == 0:
            embed = auxiliary.prepare_deny_embed(
                f"No actions for the user {user.name} could be found"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        view = ui.PaginateView()
        await view.send(
            interaction.channel, interaction.user, embeds, interaction, ephemeral=True
        )

    @modlog_group.command(
        name="lookup-moderator",
        description="Looks up the mod actions taken by a given moderator",
        extras={"ephemeral_error": True},
    )
    async def lookup_moderator_command(
        self: Self, interaction: discord.Interaction, moderator: discord.Member
    ) -> None:
        """This is the core of the /modlog lookup-moderator command

        Args:
            interaction (discord.Interaction): The interaction that called the command
            moderator (discord.Member): The moderator to search for bans for
        """
        await interaction.response.defer(ephemeral=True)

        all_action_for_user = (
            await self.bot.models.ModLog.query.where(
                self.bot.models.ModLog.guild_id == str(interaction.guild.id)
            )
            .where(self.bot.models.ModLog.moderator_id == str(moderator.id))
            .order_by(self.bot.models.ModLog.action_time.desc())
            .gino.all()
        )

        embeds = []
        embed = discord.Embed(title=f"Actions by {moderator.name}")
        embed.color = discord.Color.red()
        for index, action in enumerate(all_action_for_user):
            if index % 10 == 0 and index > 0:
                embeds.append(embed)
                embed = discord.Embed(title=f"Actions by {moderator.name}")
                embed.color = discord.Color.red()
            embed.add_field(
                name=f"Case {action.guild_case_id} | {action.action.title()}",
                value=(
                    f"Member ID: {action.member_id}\n"
                    f"Reason: {action.reason if action.reason else "No reason specified"}\n"
                    f"<t:{int(action.action_time.timestamp())}>"
                ),
                inline=False,
            )
        embeds.append(embed)

        if len(embeds) == 0:
            embed = auxiliary.prepare_deny_embed(
                f"No actions for the user {moderator.name} could be found"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        view = ui.PaginateView()
        await view.send(
            interaction.channel, interaction.user, embeds, interaction, ephemeral=True
        )

    @modlog_group.command(
        name="lookup",
        description="Looks up a case by the given id",
        extras={"ephemeral_error": True},
    )
    async def lookup_case_command(
        self: Self, interaction: discord.Interaction, case_number: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        case = (
            await self.bot.models.ModLog.query.where(
                self.bot.models.ModLog.guild_id == str(interaction.guild.id)
            )
            .where(self.bot.models.ModLog.guild_case_id == case_number)
            .gino.first()
        )
        if not case:
            embed = auxiliary.prepare_deny_embed(
                f"The case number {case_number} could not be found"
            )
        else:
            embed = await generate_action_embed(self.bot, case)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(
        self: Self, entry: discord.AuditLogEntry
    ) -> None:
        """This is monitoring for certain events that otherwise cannot be tracked
        Tracks: Kicks, (Un)bans, (Un)timeouts, (Un)mutes, (Un)deafs

        Args:
            entry (discord.AuditLogEntry): The audit log event
        """
        if not self.extension_enabled(entry.guild):
            return

        if entry.action == discord.AuditLogAction.kick:
            moderator = await self.bot.fetch_user(entry.user_id)

            if not moderator or moderator.bot:
                return

            await log_action(
                bot=self.bot,
                action_type="kick",
                guild=entry.guild,
                member=entry.target,
                moderator=moderator,
                reason=entry.reason,
            )
        elif entry.action == discord.AuditLogAction.ban:
            moderator = await self.bot.fetch_user(entry.user_id)

            if not moderator or moderator.bot:
                return

            await log_action(
                bot=self.bot,
                action_type="ban",
                guild=entry.guild,
                member=entry.target,
                moderator=moderator,
                reason=entry.reason,
            )
        elif entry.action == discord.AuditLogAction.unban:
            moderator = await self.bot.fetch_user(entry.user_id)

            if not moderator or moderator.bot:
                return

            await log_action(
                bot=self.bot,
                action_type="unban",
                guild=entry.guild,
                member=entry.target,
                moderator=moderator,
                reason=entry.reason,
            )
        elif entry.action == discord.AuditLogAction.member_update:
            # Since discord throws a ton of actions into member update, we must monitor it
            # We are looking for time out, server deaf/mute
            # This is NOT for native automod actions. Because why be even slightly consistent
            moderator = await self.bot.fetch_user(entry.user_id)

            print(moderator)

            if not moderator or moderator.bot:
                return

            before_timeout = getattr(entry.before, "timed_out_until", None)
            after_timeout = getattr(entry.after, "timed_out_until", None)
            before_deaf = getattr(entry.before, "deaf", None)
            after_deaf = getattr(entry.after, "deaf", None)
            before_mute = getattr(entry.before, "mute", None)
            after_mute = getattr(entry.after, "mute", None)

            # Mute
            if after_timeout:
                await log_action(
                    bot=self.bot,
                    action_type="timeout",
                    guild=entry.guild,
                    member=entry.target,
                    moderator=moderator,
                    reason=entry.reason,
                    expires_at=entry.after.timed_out_until,
                )
            elif before_timeout and not after_timeout:
                await log_action(
                    bot=self.bot,
                    action_type="untimeout",
                    guild=entry.guild,
                    member=entry.target,
                    moderator=moderator,
                    reason=entry.reason,
                )

            # Server Deafened
            if after_deaf and not before_deaf:
                await log_action(
                    bot=self.bot,
                    action_type="deaf",
                    guild=entry.guild,
                    member=entry.target,
                    moderator=moderator,
                    reason=entry.reason,
                )
            elif before_deaf and not after_deaf:
                await log_action(
                    bot=self.bot,
                    action_type="undeaf",
                    guild=entry.guild,
                    member=entry.target,
                    moderator=moderator,
                    reason=entry.reason,
                )

            # Server Muted
            if after_mute and not before_mute:
                await log_action(
                    bot=self.bot,
                    action_type="mute",
                    guild=entry.guild,
                    member=entry.target,
                    moderator=moderator,
                    reason=entry.reason,
                )
            elif before_mute and not after_mute:
                await log_action(
                    bot=self.bot,
                    action_type="unmute",
                    guild=entry.guild,
                    member=entry.target,
                    moderator=moderator,
                    reason=entry.reason,
                )

    @commands.Cog.listener()
    async def on_automod_action(self: Self, execution: discord.AutoModAction) -> None:
        """This monitors native auto mod executions
        This must log everything native automod does
            since native automod does't trigger other logs

        This is called for every individual action taken. So blocking,
            alerting and muting will call this 3 times.

        Args:
            execution (discord.AutoModAction): The action that automod has taken
        """
        # I hate everything about this
        rule = await execution.fetch_rule()
        member = await self.bot.fetch_user(execution.user_id)
        if any(
            action.type == discord.AutoModRuleActionType.timeout
            for action in rule.actions
        ):
            if execution.action.type == discord.AutoModRuleActionType.timeout:
                expires_at = (
                    datetime.datetime.now(datetime.UTC) + execution.action.duration
                )
                await log_action(
                    bot=self.bot,
                    action_type="timeout",
                    guild=rule.guild,
                    member=member,
                    reason=rule.name,
                    expires_at=expires_at,
                    data=f"**Violating content:** {execution.content[:200]}",
                )
        elif any(
            action.type == discord.AutoModRuleActionType.block_member_interactions
            for action in rule.actions
        ):
            if (
                execution.action.type
                == discord.AutoModRuleActionType.block_member_interactions
            ):
                await log_action(
                    bot=self.bot,
                    action_type="quarantine",
                    guild=rule.guild,
                    member=member,
                    reason=rule.name,
                    data=f"**Violating name:** {member.display_name}",
                )
        elif any(
            action.type == discord.AutoModRuleActionType.block_message
            for action in rule.actions
        ):
            if execution.action.type == discord.AutoModRuleActionType.block_message:
                await log_action(
                    bot=self.bot,
                    action_type="automod block",
                    guild=rule.guild,
                    member=member,
                    reason=rule.name,
                    data=f"**Violating name:** {member.display_name}",
                )
        else:
            await log_action(
                bot=self.bot,
                action_type="automod notice",
                guild=rule.guild,
                member=member,
                reason=rule.name,
                data=f"**Violating content:** {execution.content[:200]}",
            )

    @commands.Cog.listener()
    async def on_member_join(self: Self, member: discord.Member) -> None:
        """This is to track unkicks, aka people joining the server back after a recent kick

        Args:
            member (discord.Member): The member who has joined the server
        """
        if not self.extension_enabled(member.guild):
            return

        most_recent_kick = (
            await self.bot.models.ModLog.query.where(
                self.bot.models.ModLog.guild_id == str(member.guild.id)
            )
            .where(self.bot.models.ModLog.member_id == str(member.id))
            .where(self.bot.models.ModLog.action == "kick")
            .order_by(self.bot.models.ModLog.guild_case_id.desc())
            .gino.first()
        )

        # No kick on record, nothing to do
        if most_recent_kick is None:
            return

        most_recent_unkick = (
            await self.bot.models.ModLog.query.where(
                self.bot.models.ModLog.guild_id == str(member.guild.id)
            )
            .where(self.bot.models.ModLog.member_id == str(member.id))
            .where(self.bot.models.ModLog.action == "unkick")
            .order_by(self.bot.models.ModLog.guild_case_id.desc())
            .gino.first()
        )

        # If they've never been marked as unkicked, this join is an unkick
        if most_recent_unkick is None:
            await log_action(
                bot=self.bot,
                action_type="unkick",
                guild=member.guild,
                member=member,
            )
            return

        # If the latest kick is newer than the latest unkick,
        # this join corresponds to that kick
        if most_recent_kick.guild_case_id > most_recent_unkick.guild_case_id:
            await log_action(
                bot=self.bot,
                action_type="unkick",
                guild=member.guild,
                member=member,
            )


async def generate_action_embed(
    bot: bot.models.ModLog, action_entry: munch.Munch
) -> discord.Embed:
    """This generates a stylized embed that displays the mod action taken and information

    Args:
        bot (bot.models.ModLog): The bot object, used to fetch information from discord
        action_entry (munch.Munch): The action entry from the database to display

    Returns:
        discord.Embed: The final embed, ready to display
    """

    embed = discord.Embed(
        title=f"Case {action_entry.guild_case_id} | {action_entry.action.title()}"
    )
    description_strs = []

    # If this action has a member punished, display if
    if action_entry.member_id:
        member_account = await bot.fetch_user(int(action_entry.member_id))
        description_strs.append(
            f"**Offender:** {member_account.name} {member_account.mention} ({member_account.id})"
        )

    # Always display the reason line, just if no reason explicilty display that
    if action_entry.reason:
        description_strs.append(f"**Reason:** {action_entry.reason}")
    else:
        description_strs.append("**Reason:** No reason specified")

    # If a moderator has been tied to this action, display that
    # If no moderator has been listed, this must be automod
    if action_entry.moderator_id:
        moderator_account = await bot.fetch_user(int(action_entry.moderator_id))
        description_strs.append(
            f"**Responsible moderator:** {moderator_account.name} {moderator_account.mention} ({moderator_account.id})"
        )
    else:
        description_strs.append("**Responsible moderator:** No associated moderator")

    # If this action has extra data, display it as is.
    if action_entry.data:
        # This might need special handling for specific events, we will see
        description_strs.append(action_entry.data)

    # If this action has an expiration date, display it
    if action_entry.until_time:
        description_strs.append(
            f"**Until:** <t:{int(action_entry.until_time.timestamp())}>"
        )

    embed.description = "\n".join(description_strs)
    embed.timestamp = action_entry.action_time
    if "un" in action_entry.action:
        embed.color = discord.Color.green()
    elif "clear" in action_entry.action:
        embed.color = discord.Color.blue()
    else:
        embed.color = discord.Color.red()

    return embed


async def get_next_case_number(
    bot: bot.TechSupportBot,
    guild: discord.Guild,
) -> int:
    """This searches the database for all cases in the given guild
    This will return the next case number to use for a given guild, or 1 if no cases exist

    Args:
        bot (bot.TechSupportBot): The bot object, used to fetch information from the database
        guild (discord.Guild): The guild to get the next number for

    Returns:
        int: The next case number to use
    """
    latest_case = (
        await bot.models.ModLog.query.where(bot.models.ModLog.guild_id == str(guild.id))
        .order_by(bot.models.ModLog.guild_case_id.desc())
        .gino.first()
    )

    if latest_case is None:
        return 1

    return latest_case.guild_case_id + 1


async def log_action(
    bot: bot.TechSupportBot,
    action_type: str,
    guild: discord.Guild,
    member: discord.abc.User | None = None,
    moderator: discord.abc.User | None = None,
    reason: str = "",
    data: str = "",
    expires_at: datetime.datetime = None,
) -> None:
    """This logs a mod action in the database, and sends it to the modlog channel

    Args:
        bot (bot.TechSupportBot): The bot object, used to access the database
        action_type (str): The action type as a string representation
        guild (discord.Guild): The guild this action occured in
        member (discord.abc.User | None, optional): The member being punished, if applicable.
        moderator (discord.abc.User | None, optional): The moderator taking action, if applicable.
        reason (str, optional): The reason this action was taken, if applicable.
        data (str, optional): Any extra data associated with this action, if applicable.
        expires_at (datetime.datetime, optional): When this action expires, if applicable.
    """
    # Log nothing if the module is disabled
    if "moderation.modlog" not in configuration.get_config_entry(
        guild.id, "core_enabled_extensions"
    ):
        return

    # If the action has a member or moderator, get the IDs
    member_id = None
    moderator_id = None
    if member:
        member_id = str(member.id)
    if moderator:
        moderator_id = str(moderator.id)

    # This is done to prevent race conditions where two actions get the same case number
    # We can detect the unique error and just try again. If so, this means
    # A new database entry was created after we got the case number
    while True:
        try:
            # We need to calculate the case ID number for this action
            case_id = await get_next_case_number(bot, guild)

            entry = bot.models.ModLog(
                guild_id=str(guild.id),
                guild_case_id=case_id,
                action=action_type,
                reason=reason,
                data=data,
                moderator_id=moderator_id,
                member_id=member_id,
                until_time=expires_at,
            )
            entry = await entry.create()
            break
        except asyncpg.UniqueViolationError:
            continue

    try:
        alert_channel = guild.get_channel(
            int(configuration.get_config_entry(guild.id, "modlog_alert_channel"))
        )
    except TypeError:
        alert_channel = None

    if not alert_channel:
        return

    embed = await generate_action_embed(bot, entry)
    await alert_channel.send(embed=embed)
