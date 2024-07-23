"""Handles the automod checks"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Self

import discord
import munch
from botlogging import LogContext, LogLevel
from commands import moderator, modlog
from core import cogs, moderation
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(AutoMod(bot=bot, extension_name="automod"))


@dataclass
class AutoModPunishment:
    """This is a base class holding the violation and recommended actions
    Since automod is a framework, the actions can translate to different things

    violation_str - The string of the policy broken. Should be displayed to user
    recommend_delete - If the policy recommends deletion of the message
    recommend_warn - If the policy recommends warning the user
    recommend_mute - If the policy recommends muting the user

    """

    violation_str: str
    recommend_delete: bool
    recommend_warn: bool
    recommend_mute: bool

    @property
    def score(self: Self) -> int:
        """A score so that the AutoModPunishment object is sortable
        This sorts based on actions recommended to be taken

        Returns:
            int: The score
        """
        score = 0
        if self.recommend_mute:
            score += 4
        if self.recommend_warn:
            score += 2
        if self.recommend_delete:
            score += 1
        return score


class AutoMod(cogs.MatchCog):
    async def match(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> bool:
        """Checks to see if a message should be considered for automod violations

        Args:
            config (munch.Munch): The config of the guild to check
            ctx (commands.Context): The context of the original message
            content (str): The string representation of the message

        Returns:
            bool: Whether the message should be inspected for automod violations
        """
        if not str(ctx.channel.id) in config.extensions.protect.channels.value:
            await self.bot.logger.send_log(
                message="Channel not in protected channels - ignoring protect check",
                level=LogLevel.DEBUG,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
            )
            return False

        role_names = [role.name.lower() for role in getattr(ctx.author, "roles", [])]

        if any(
            role_name.lower() in role_names
            for role_name in config.extensions.protect.bypass_roles.value
        ):
            return False

        if ctx.author.id in config.extensions.protect.bypass_ids.value:
            return False

        return True

    async def response(
        self, config: munch.Munch, ctx: commands.Context, content: str, result: bool
    ) -> None:
        """Handles a discord automod violation

        Args:
            config (munch.Munch): The config of the guild where the message was sent
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message
            result (bool): What the match() function returned
        """
        should_delete = False
        should_warn = False
        should_mute = False

        all_punishments = run_all_checks(config, ctx.message)

        if len(all_punishments) == 0:
            return

        sorted_punishments = sorted(
            all_punishments, key=lambda p: p.score, reverse=True
        )
        for punishment in sorted_punishments:
            should_delete = should_delete or punishment.recommend_delete
            should_warn = should_warn or punishment.recommend_warn
            should_mute = should_mute or punishment.recommend_mute

        actions = []

        reason_str = sorted_punishments[0].violation_str

        if should_mute:
            actions.append("mute")
            if not ctx.author.timed_out_until:
                await ctx.author.timeout(
                    timedelta(hours=1),
                    reason=sorted_punishments[0].violation_str,
                )

        if should_delete:
            actions.append("delete")
            await ctx.message.delete()

        if should_warn:
            actions.append("warn")
            count_of_warnings = (
                len(await moderation.get_all_warnings(self.bot, ctx.author, ctx.guild))
                + 1
            )
            reason_str += f" ({count_of_warnings} total warnings)"
            await moderation.warn_user(
                self.bot, ctx.author, ctx.author, sorted_punishments[0].violation_str
            )
            if count_of_warnings >= config.extensions.protect.max_warnings.value:
                ban_embed = moderator.generate_response_embed(
                    ctx.author,
                    "ban",
                    reason=(
                        f"Over max warning count {count_of_warnings} out of"
                        f" {config.extensions.protect.max_warnings.value} (final warning:"
                        f" {sorted_punishments[0].violation_str}) - banned by automod"
                    ),
                )

                await ctx.send(content=ctx.author.mention, embed=ban_embed)
                try:
                    await ctx.author.send(embed=ban_embed)
                except discord.Forbidden:
                    await self.bot.logger.send_log(
                        message=f"Could not DM {ctx.author} about being banned",
                        level=LogLevel.WARNING,
                        context=LogContext(guild=ctx.guild, channel=ctx.channel),
                    )

                await moderation.ban_user(
                    ctx.guild, ctx.author, 7, sorted_punishments[0].violation_str
                )
                await modlog.log_ban(
                    self.bot,
                    ctx.author,
                    ctx.guild.me,
                    ctx.guild,
                    sorted_punishments[0].violation_str,
                )

        if len(actions) == 0:
            actions.append("notice")

        actions_str = " & ".join(actions)

        embed = moderator.generate_response_embed(ctx.author, actions_str, reason_str)

        await ctx.send(content=ctx.author.mention, embed=embed)
        try:
            await ctx.author.send(embed=embed)
        except discord.Forbidden:
            await self.bot.logger.send_log(
                message=f"Could not DM {ctx.author} about being automodded",
                level=LogLevel.WARNING,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
            )

        alert_channel_embed = generate_automod_alert_embed(
            ctx, sorted_punishments, actions_str
        )

        config = self.bot.guild_configs[str(ctx.guild.id)]

        try:
            alert_channel = ctx.guild.get_channel(
                int(config.extensions.protect.alert_channel.value)
            )
        except TypeError:
            alert_channel = None

        if not alert_channel:
            return

        await alert_channel.send(embed=alert_channel_embed)

    @commands.Cog.listener()
    async def on_raw_message_edit(self: Self, payload: discord.RawMessageUpdateEvent):
        """This is called when any message is edited in any guild the bot is in.
        There is no guarantee that the message exists or is used

        Args:
            payload (discord.RawMessageUpdateEvent): The raw event that the edit generated
        """
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        config = self.bot.guild_configs[str(guild.id)]
        if not self.extension_enabled(config):
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message:
            return

        # Don't trigger if content hasn't changed
        if payload.cached_message and payload.cached_message.content == message.content:
            return

        ctx = await self.bot.get_context(message)
        matched = await self.match(config, ctx, message.content)
        if not matched:
            return

        await self.response(config, ctx, message.content, matched)


def generate_automod_alert_embed(
    ctx: commands.Context, violations: list[AutoModPunishment], action_taken: str
):
    """Generates an alert embed for the automod rules that are broken

    Args:
        ctx (commands.Context): The context of the message that violated the automod
        violations (list[AutoModPunishment]): The list of all violations of the automod
        action_taken (str): The text based action taken against the user

    Returns:
        discord.Embed: The formatted embed ready to be sent to discord
    """

    ALERT_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/2063/PNG/512/"
        + "alert_danger_warning_notification_icon_124692.png"
    )

    embed = discord.Embed(
        title="Automod Violations",
        description="\n".join(violation.violation_str for violation in violations),
    )
    embed.add_field(name="Actions Taken", value=action_taken)
    embed.add_field(name="Channel", value=f"{ctx.channel.mention} ({ctx.channel.name})")
    embed.add_field(name="User", value=f"{ctx.author.mention} ({ctx.author.name})")
    embed.add_field(name="Message", value=ctx.message.content, inline=False)
    embed.add_field(name="URL", value=ctx.message.jump_url, inline=False)

    embed.set_thumbnail(url=ALERT_ICON_URL)
    embed.color = discord.Color.red()

    return embed


# Automod will only ever be a framework to say something needs to be done
# Outside of running from the response function, NO ACTION will be taken
# All checks will return a list of AutoModPunishment, which may be nothing


def run_all_checks(
    config: munch.Munch, message: discord.Message
) -> list[AutoModPunishment]:
    """This runs all 4 checks on a given discord.Message
    handle_file_extensions
    handle_mentions
    handle_exact_string
    handle_regex_string

    Args:
        config (munch.Munch): The guild config to check with
        message (discord.Message): The message object to use to search

    Returns:
        list[AutoModPunishment]: The automod violations that the given message violated
    """
    all_violations = (
        run_only_string_checks(config, message.clean_content)
        + handle_file_extensions(config, message.attachments)
        + handle_mentions(config, message)
    )
    return all_violations


def run_only_string_checks(
    config: munch.Munch, content: str
) -> list[AutoModPunishment]:
    """This runs the plaintext string texts and returns the combined list of violations
    handle_exact_string
    handle_regex_string

    Args:
        config (munch.Munch): The guild config to check with
        content (str): The content of the message to search

    Returns:
        list[AutoModPunishment]: The automod violations that the given message violated
    """
    all_violations = handle_exact_string(config, content) + handle_regex_string(
        config, content
    )
    return all_violations


def handle_file_extensions(
    config: munch.Munch, attachments: list[discord.Attachment]
) -> list[AutoModPunishment]:
    """This checks a list of attachments for attachments that violate the automod rules

    Args:
        config (munch.Munch): The guild config to check with
        attachments (list[discord.Attachment]): The list of attachments to search

    Returns:
        list[AutoModPunishment]: The automod violations that the given message violated
    """
    violations = []
    for attachment in attachments:
        if (
            attachment.filename.split(".")[-1]
            in config.extensions.protect.banned_file_extensions.value
        ):
            violations.append(
                AutoModPunishment(
                    f"{attachment.filename} has a suspicious file extension",
                    recommend_delete=True,
                    recommend_warn=True,
                    recommend_mute=False,
                )
            )
    return violations


def handle_mentions(
    config: munch.Munch, message: discord.Message
) -> list[AutoModPunishment]:
    """This checks a given discord message to make sure it doesn't violate the mentions maximum

    Args:
        config (munch.Munch): The guild config to check with
        message (discord.Message): The message to check for mentions with

    Returns:
        list[AutoModPunishment]: The automod violations that the given message violated
    """
    if len(message.mentions) > config.extensions.protect.max_mentions.value:
        return [
            AutoModPunishment(
                "Mass Mentions",
                recommend_delete=True,
                recommend_warn=True,
                recommend_mute=False,
            )
        ]
    return []


def handle_exact_string(config: munch.Munch, content: str) -> list[AutoModPunishment]:
    """This checks the configued automod exact string blocks
    If the content matches the string, it's added to a list

    Args:
        config (munch.Munch): The guild config to check with
        content (str): The content of the message to search

    Returns:
        list[AutoModPunishment]: The automod violations that the given message violated
    """
    violations = []
    for (
        keyword,
        filter_config,
    ) in config.extensions.protect.string_map.value.items():
        if keyword.lower() in content.lower():
            violations.append(
                AutoModPunishment(
                    filter_config.message,
                    filter_config.delete,
                    filter_config.warn,
                    filter_config.mute,
                )
            )
    return violations


def handle_regex_string(config: munch.Munch, content: str) -> list[AutoModPunishment]:
    """This checks the configued automod regex blocks
    If the content matches the regex, it's added to a list

    Args:
        config (munch.Munch): The guild config to check with
        content (str): The content of the message to search

    Returns:
        list[AutoModPunishment]: The automod violations that the given message violated
    """
    violations = []
    for (
        _,
        filter_config,
    ) in config.extensions.protect.string_map.value.items():
        regex = filter_config.get("regex")
        if regex:
            try:
                match = re.search(regex, content)
            except re.error:
                match = None
            if match:
                violations.append(
                    AutoModPunishment(
                        filter_config.message,
                        filter_config.delete,
                        filter_config.warn,
                        filter_config.mute,
                    )
                )
    return violations
