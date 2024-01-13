from __future__ import annotations

import io
from typing import TYPE_CHECKING

import discord
from botlogging import LogContext, LogLevel
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


class AutoMod(cogs.MatchCog):
    async def match(self, config, ctx, content):
        ...
    
    async def response(self, config, ctx, content, _):
        ...
    

    async def run_all_checks(self, message: discord.Message) -> bool:
        ...
    
    async def run_only_string_checks(self, content: str, member: discord.Member) -> bool:
        ...
    
    async def handle_file_extensions(self, attachments: list[discord.Attachment]) -> bool:
        ...
    
    async def handle_mentions(self, message: discord.Message) -> bool:
        ...
    
    async def handle_exact_string(self, content: str) -> bool:
        ...
    
    async def handle_regex_string(self, content: str) -> bool:
        ...

    async def should_ban_or_warn(self, member: discord.Member):
        ...