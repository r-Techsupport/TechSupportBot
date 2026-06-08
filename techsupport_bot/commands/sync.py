"""
Commands which allows the app command tree to be updated
The cog in the file is named:
    AppCommandSync

This file contains 1 commands:
    .sync
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Sync plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(AppCommandSync(bot=bot))


class AppCommandSync(cogs.BaseCog):
    """
    The class that holds the sync command
    """

    @commands.check(auxiliary.bot_admin_check_context)
    @auxiliary.with_typing
    @commands.command(
        name="sync",
        description="Syncs slash commands",
        usage="",
    )
    async def sync_slash_commands(self: Self, ctx: commands.Context) -> None:
        """A simple command to manually sync slash commands

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        synced = await self.bot.tree.sync()
        await auxiliary.send_confirm_embed(
            message=(
                "Successfully updated the slash command tree. Currently there are"
                f" {len(synced)} commands in the tree"
            ),
            channel=ctx.channel,
        )
