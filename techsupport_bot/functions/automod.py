from __future__ import annotations

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
    ) -> bool:
        ...

    async def response(
        self, config: munch.Munch, ctx: commands.Context, content: str, result: bool
    ) -> None:
        ...

    async def should_ban_instead_of_warn(self, member: discord.Member) -> bool:
        ...

    async def send_automod_alert(
        self, message: discord.Message, violation: AutoModPunishment
    ) -> None:
        ...


async def run_all_checks(
    guild: discord.Guild, config, message: discord.Message
) -> list[AutoModPunishment]:
    # Automod will only ever be a framework to say something needs to be done
    # Outside of running from the response function, NO ACTION will be taken
    # All checks will return a list of AutoModPunishment, which may be nothing
    ...


async def run_only_string_checks(
    guild: discord.Guild, config, content: str
) -> list[AutoModPunishment]:
    ...


async def handle_file_extensions(
    guild: discord.Guild, config, attachments: list[discord.Attachment]
) -> list[AutoModPunishment]:
    ...


async def handle_mentions(
    guild: discord.Guild, config, message: discord.Message
) -> list[AutoModPunishment]:
    ...


async def handle_exact_string(
    guild: discord.Guild, config, content: str
) -> list[AutoModPunishment]:
    ...


async def handle_regex_string(
    guild: discord.Guild, config, content: str
) -> list[AutoModPunishment]:
    ...
