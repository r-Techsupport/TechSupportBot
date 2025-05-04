"""
Commands: /hello
Config: None
Databases: None
Unit tests: No need
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the ChatGPT plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Greeter(bot=bot))


class Greeter(cogs.BaseCog):
    """Class for the greeter command."""

    @app_commands.command(
        name="hello",
        description="Says hello to the bot (because they are doing such a great job!)",
        extras={"module": "hello"},
    )
    async def hello_app_command(self: Self, interaction: discord.Interaction) -> None:
        """A simple command to have the bot say HEY to the invoker

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        await interaction.response.send_message("🇭 🇪 🇾")
