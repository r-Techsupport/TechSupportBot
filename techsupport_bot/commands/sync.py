from base import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(AppCommandSync(bot=bot))


class AppCommandSync(cogs.BaseCog):
    ADMIN_ONLY = True

    @auxiliary.with_typing
    @commands.command(
        name="sync",
        description="Syncs slash commands",
        usage="",
    )
    async def sync_slash_commands(self, ctx):
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
