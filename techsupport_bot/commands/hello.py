"""
Module for the hello command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from core import auxiliary, cogs
from discord.ext import commands

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

    async def hello_command(self: Self, ctx: commands.Context) -> None:
        """A simple function to add HEY reactions to the command invocation

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        await auxiliary.add_list_of_reactions(
            message=ctx.message, reactions=["🇭", "🇪", "🇾"]
        )

    @commands.command(
        name="hello",
        brief="Says hello to the bot",
        description="Says hello to the bot (because they are doing such a great job!)",
        usage="",
    )
    async def hello(self: Self, ctx: commands.Context) -> None:
        """Entry point for the .hello command on discord

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        await self.hello_command(ctx)
