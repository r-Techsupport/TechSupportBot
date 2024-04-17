"""
Commands which allows the app command tree to be updated
The cog in the file is named:
    AppCommandSync

This file contains 1 commands:
    .sync
"""

from core import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Registers the AppCommandSync Cog"""
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
    async def sync_slash_commands(self, ctx: commands.Context):
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
