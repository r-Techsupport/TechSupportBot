"""The file that holds the honeypot function"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Self

import discord
import munch
from botlogging import LogContext, LogLevel
from core import cogs, extensionconfig
from discord.ext import commands
from functions import automod

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
        title="Honeypot channels",
        description=("The list of channel ID's that are honeypots"),
        default=[],
    )
    await bot.add_cog(HoneyPot(bot=bot, extension_name="honeypot"))
    bot.add_extension_config("honeypot", config)


class HoneyPot(cogs.MatchCog):
    """The pasting module"""

    async def match(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> bool:
        """Checks to see if a message should be considered for a paste

        Args:
            config (munch.Munch): The config of the guild to check
            ctx (commands.Context): The context of the original message
            content (str): The string representation of the message

        Returns:
            bool: Whether the message should be inspected for a paste
        """
        # If the channel isn't a honeypot, do nothing.
        if not str(ctx.channel.id) in config.extensions.honeypot.channels.value:
            return False
        return True

    async def response(
        self: Self,
        config: munch.Munch,
        ctx: commands.Context,
        content: str,
        result: bool,
    ) -> None:
        """Handles a paste check

        Args:
            config (munch.Munch): The config of the guild where the message was sent
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message
            result (bool): What the match() function returned
        """
        # Temporary ban and unban.
        # This should be replaced with a guild wide purge when discord.py can be updated.
        await ctx.author.ban(delete_message_days=1, reason="triggered honeypot")
        await ctx.guild.unban(ctx.author, reason="triggered honeypot")
