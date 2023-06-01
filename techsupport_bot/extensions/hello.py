"""
Module for the hello command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

import base
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Add the hello greeter to the config file."""
    await bot.add_cog(Greeter(bot=bot))


class Greeter(base.BaseCog):
    """Class for the greeter command."""

    async def hello_command(self, ctx) -> None:
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
    async def hello(self, ctx):
        """Method to respond to hellos by the bot."""
        await self.hello_command(ctx)
