from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
import munch
from botlogging import LogContext, LogLevel
from commands import moderator
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
    def score(self) -> int:
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
        self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> bool:
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
        if should_mute:
            actions.append("mute")
        if should_warn:
            actions.append("warn")
        if should_delete:
            actions.append("delete")

        if len(actions) == 0:
            actions.append("notice")

        actions_str = " & ".join(actions)

        embed = moderator.generate_response_embed(
            ctx.author, actions_str, sorted_punishments[0].violation_str
        )

        if should_mute and not ctx.author.timed_out_until:
            await ctx.author.timeout(
                timedelta(hours=1),
                reason=sorted_punishments[0].violation_str,
            )

        if should_delete:
            await ctx.message.delete()

        if should_warn:
            await moderation.warn_user(
                self.bot, ctx.author, ctx.author, sorted_punishments[0].violation_str
            )

            count_of_warnings = (
                len(await moderation.get_all_warnings(self.bot, ctx.author, ctx.guild))
                + 1
            )

            if count_of_warnings >= config.extensions.protect.max_warnings.value:
                await moderation.ban_user(
                    ctx.guild, ctx.author, 7, sorted_punishments[0].violation_str
                )

        await ctx.send(embed=embed)


def run_all_checks(config, message: discord.Message) -> list[AutoModPunishment]:
    # Automod will only ever be a framework to say something needs to be done
    # Outside of running from the response function, NO ACTION will be taken
    # All checks will return a list of AutoModPunishment, which may be nothing
    all_violations = (
        run_only_string_checks(config, message.clean_content)
        + handle_file_extensions(config, message.attachments)
        + handle_mentions(config, message)
    )
    return all_violations


def run_only_string_checks(config, content: str) -> list[AutoModPunishment]:
    all_violations = handle_exact_string(config, content) + handle_regex_string(
        config, content
    )
    return all_violations


def handle_file_extensions(
    config, attachments: list[discord.Attachment]
) -> list[AutoModPunishment]:
    violations = []
    for attachment in attachments:
        if (
            attachment.filename.split(".")[-1]
            in config.extensions.protect.banned_file_extensions.value
        ):
            violations.append(
                AutoModPunishment(
                    f"{attachment.filename} has a suspicious file extension",
                    True,
                    True,
                    False,
                )
            )
    return violations


def handle_mentions(config, message: discord.Message) -> list[AutoModPunishment]:
    if len(message.mentions) > config.extensions.protect.max_mentions.value:
        return [AutoModPunishment("Mass Mentions", True, True, False)]
    return []


def handle_exact_string(config, content: str) -> list[AutoModPunishment]:
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


def handle_regex_string(config, content: str) -> list[AutoModPunishment]:
    violations = []
    for (
        keyword,
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
