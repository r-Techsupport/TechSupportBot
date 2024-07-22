from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
import munch
from core import cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(AutoMod(bot=bot))


@dataclass
class AutoModPunishment:
    """This is a base class holding the violation and recommended actions
    Since automod is a framework, the actions can translate to different things

    violation_str - The string of the policy broken. Should be displayed to user
    recommend_delete - If the policy recommends deletion of the message
    recommend_warn - If the policy recommends warning the user

    """

    violation_str: str
    recommend_delete: bool
    recommend_warn: bool


class AutoMod(cogs.MatchCog):
    async def match(
        self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> bool: ...

    async def response(
        self, config: munch.Munch, ctx: commands.Context, content: str, result: bool
    ) -> None: ...

    async def should_ban_instead_of_warn(self, member: discord.Member) -> bool: ...

    async def send_automod_alert(
        self, message: discord.Message, violation: AutoModPunishment
    ) -> None: ...


def run_all_checks(config, message: discord.Message) -> list[AutoModPunishment]:
    # Automod will only ever be a framework to say something needs to be done
    # Outside of running from the response function, NO ACTION will be taken
    # All checks will return a list of AutoModPunishment, which may be nothing
    ...


def run_only_string_checks(config, content: str) -> list[AutoModPunishment]: ...


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
                    f"{attachment.filename} has a suspicious file extension", True, True
                )
            )
    return violations


def handle_mentions(config, message: discord.Message) -> list[AutoModPunishment]:
    if len(message.mentions) > config.extensions.protect.max_mentions.value:
        return [AutoModPunishment("Mass Mentions", True, True)]
    return []


def handle_exact_string(config, content: str) -> list[AutoModPunishment]:
    violations = []
    for rule in config.extensions.protect.block_strings.value:
        if rule.string.lower() in content.lower():
            violations.append(AutoModPunishment(rule.message, rule.delete, rule.warn))
    return violations


def handle_regex_string(config, content: str) -> list[AutoModPunishment]:
    violations = []
    for rule in config.extensions.protect.block_strings.value:
        regex = rule.get("regex")
        if regex:
            try:
                match = re.search(regex, content)
            except re.error:
                match = None
            if match:
                violations.append(
                    AutoModPunishment(rule.message, rule.delete, rule.warn)
                )
    return violations
