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
from core import cogs, extensionconfig, moderation
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
        key="channels",
        datatype="list",
        title="Protected channels",
        description=(
            "The list of channel ID's associated with the channels to auto-protect"
        ),
        default=[],
    )
    config.add(
        key="bypass_roles",
        datatype="list",
        title="Bypassed role names",
        description=(
            "The list of role names associated with bypassed roles by the auto-protect"
        ),
        default=[],
    )
    config.add(
        key="string_map",
        datatype="dict",
        title="Keyword string map",
        description=(
            "Mapping of keyword strings to data defining the action taken by"
            " auto-protect"
        ),
        default={},
    )
    config.add(
        key="banned_file_extensions",
        datatype="dict",
        title="List of banned file types",
        description=(
            "A list of all file extensions to be blocked and have a auto warning issued"
        ),
        default=[],
    )
    config.add(
        key="alert_channel",
        datatype="int",
        title="Alert channel ID",
        description="The ID of the channel to send auto-protect alerts to",
        default=None,
    )
    config.add(
        key="max_mentions",
        datatype="int",
        title="Max message mentions",
        description=(
            "Max number of mentions allowed in a message before triggering auto-protect"
        ),
        default=3,
    )
    await bot.add_cog(AutoMod(bot=bot, extension_name="automod"))
    bot.add_extension_config("automod", config)


@dataclass
class AutoModPunishment:
    """This is a base class holding the violation and recommended actions
    Since automod is a framework, the actions can translate to different things

    Attrs:
        violation_str (str): The string of the policy broken. Should be displayed to user
        recommend_delete (bool): If the policy recommends deletion of the message
        recommend_warn (bool): If the policy recommends warning the user
        recommend_mute (int): If the policy recommends muting the user.
            If so, the amount of seconds to mute for.
        is_silent (bool, optional): If the punishment should be silent. Defaults to False
        score (int): The weighted score for sorting punishments

    """

    violation_str: str
    recommend_delete: bool
    recommend_warn: bool
    recommend_mute: int
    is_silent: bool = False

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


@dataclass
class AutoModAction:
    """The final summarized action for this automod violation

    Attrs:
        warn (bool): Whether the user should be warned
        delete_message (bool): Whether the message should be deleted
        mute (bool): Whether the user should be muted
        mute_duration (int): How many seconds to mute the user for
        be_silent (bool): If the actions should be taken silently
        action_string (str): The string of & separated actions taken
        violation_string (str): The most severe punishment to be used as a reason
        total_punishments (str): All the punishment reasons
        violations_list (list[AutoModPunishment]): The list of original AutoModPunishment items

    """

    warn: bool
    delete_message: bool
    mute: bool
    mute_duration: int
    be_silent: bool
    action_string: str
    violation_string: str
    total_punishments: str
    violations_list: list[AutoModPunishment]


class AutoMod(cogs.MatchCog):
    """Holds all of the discord message specific automod functions
    Most of the automod is a class function"""

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
        if not str(ctx.channel.id) in config.extensions.automod.channels.value:
            await self.bot.logger.send_log(
                message="Channel not in automod channels - ignoring automod check",
                level=LogLevel.DEBUG,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
            )
            return False

        role_names = [role.name.lower() for role in getattr(ctx.author, "roles", [])]

        if any(
            role_name.lower() in role_names
            for role_name in config.extensions.automod.bypass_roles.value
        ):
            return False

        return True

    async def response(
        self: Self,
        config: munch.Munch,
        ctx: commands.Context,
        content: str,
        result: bool,
    ) -> None:
        """Handles a discord automod violation

        Args:
            config (munch.Munch): The config of the guild where the message was sent
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message
            result (bool): What the match() function returned
        """
        all_punishments = run_all_checks(config, ctx.message)

        if len(all_punishments) == 0:
            return

        total_punishment = process_automod_violations(all_punishments=all_punishments)

        if total_punishment.mute > 0:
            await moderation.mute_user(
                user=ctx.author,
                reason=total_punishment.violation_string,
                duration=timedelta(seconds=total_punishment.mute_duration),
            )

        if total_punishment.delete_message:
            await ctx.message.delete()

        if total_punishment.warn:
            count_of_warnings = (
                len(await moderation.get_all_warnings(self.bot, ctx.author, ctx.guild))
                + 1
            )
            total_punishment.violation_string += (
                f" ({count_of_warnings} total warnings)"
            )
            await moderation.warn_user(
                self.bot, ctx.author, ctx.author, total_punishment.violation_string
            )
            if count_of_warnings >= config.moderation.max_warnings:
                ban_embed = moderator.generate_response_embed(
                    ctx.author,
                    "ban",
                    reason=(
                        f"Over max warning count {count_of_warnings} out of"
                        f" {config.moderation.max_warnings} (final warning:"
                        f" {total_punishment.violation_string}) - banned by automod"
                    ),
                )
                if not total_punishment.be_silent:
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
                    ctx.guild, ctx.author, 7, total_punishment.violation_string
                )
                await modlog.log_ban(
                    self.bot,
                    ctx.author,
                    ctx.guild.me,
                    ctx.guild,
                    total_punishment.violation_string,
                )

        if total_punishment.be_silent:
            return

        embed = moderator.generate_response_embed(
            ctx.author,
            total_punishment.action_string,
            total_punishment.violation_string,
        )

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
            ctx, total_punishment.total_punishments, total_punishment.action_string
        )

        config = self.bot.guild_configs[str(ctx.guild.id)]

        try:
            alert_channel = ctx.guild.get_channel(
                int(config.extensions.automod.alert_channel.value)
            )
        except TypeError:
            alert_channel = None

        if not alert_channel:
            return

        await alert_channel.send(embed=alert_channel_embed)

    @commands.Cog.listener()
    async def on_raw_message_edit(
        self: Self, payload: discord.RawMessageUpdateEvent
    ) -> None:
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


def process_automod_violations(
    all_punishments: list[AutoModPunishment],
) -> AutoModAction:
    """This processes a list of potentially many AutoModPunishments into a single
    recommended action

    Args:
        all_punishments (list[AutoModPunishment]): The list of punishments that should be taken

    Returns:
        AutoModAction: The final summarized action that is recommended to be taken
    """
    if len(all_punishments) == 0:
        return None

    should_delete = False
    should_warn = False
    mute_duration = 0

    silent = True

    sorted_punishments = sorted(all_punishments, key=lambda p: p.score, reverse=True)
    for punishment in sorted_punishments:
        should_delete = should_delete or punishment.recommend_delete
        should_warn = should_warn or punishment.recommend_warn
        mute_duration = max(mute_duration, punishment.recommend_mute)

        if not punishment.is_silent:
            silent = False

    actions = []

    reason_str = sorted_punishments[0].violation_str

    if mute_duration > 0:
        actions.append("mute")

    if should_delete:
        actions.append("delete")

    if should_warn:
        actions.append("warn")

    if len(actions) == 0:
        actions.append("notice")

    actions_str = " & ".join(actions)

    all_alerts_str = "\n".join(violation.violation_str for violation in all_punishments)

    final_action = AutoModAction(
        warn=should_warn,
        delete_message=should_delete,
        mute=mute_duration > 0,
        mute_duration=mute_duration,
        be_silent=silent,
        action_string=actions_str,
        violation_string=reason_str,
        total_punishments=all_alerts_str,
        violations_list=all_punishments,
    )

    return final_action


def generate_automod_alert_embed(
    ctx: commands.Context, violations: str, action_taken: str
) -> discord.Embed:
    """Generates an alert embed for the automod rules that are broken

    Args:
        ctx (commands.Context): The context of the message that violated the automod
        violations (str): The string form of ALL automod violations the user triggered
        action_taken (str): The text based action taken against the user

    Returns:
        discord.Embed: The formatted embed ready to be sent to discord
    """

    ALERT_ICON_URL: str = (
        "https://www.iconarchive.com/download/i76061/martz90/circle-addon2/warning.512.png"
    )

    embed = discord.Embed(
        title="Automod Violations",
        description=violations,
    )
    embed.add_field(name="Actions Taken", value=action_taken)
    embed.add_field(name="Channel", value=f"{ctx.channel.mention} ({ctx.channel.name})")
    embed.add_field(
        name="User", value=f"{ctx.author.mention} ({ctx.author.name}, {ctx.author.id})"
    )
    embed.add_field(name="Message", value=ctx.message.content[:1024], inline=False)
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
            in config.extensions.automod.banned_file_extensions.value
        ):
            violations.append(
                AutoModPunishment(
                    f"{attachment.filename} has a suspicious file extension",
                    recommend_delete=True,
                    recommend_warn=True,
                    recommend_mute=0,
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
    if len(message.mentions) > config.extensions.automod.max_mentions.value:
        return [
            AutoModPunishment(
                "Mass Mentions",
                recommend_delete=True,
                recommend_warn=True,
                recommend_mute=0,
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
    ) in config.extensions.automod.string_map.value.items():
        if keyword.lower() in content.lower():
            violations.append(
                AutoModPunishment(
                    filter_config.message,
                    filter_config.delete,
                    filter_config.warn,
                    filter_config.mute,
                    filter_config.silent_punishment,
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
    ) in config.extensions.automod.string_map.value.items():
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
                        filter_config.silent_punishment,
                    )
                )
    return violations
