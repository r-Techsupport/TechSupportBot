import cogs
import discord
from discord.ext import commands


def setup(bot):
    bot.add_cog(Moderator(bot))


class Moderator(cogs.BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False

    @commands.group()
    async def purge(self, ctx):
        pass

    @commands.has_permissions(manage_messages=True)
    @purge.command(
        name="x",
        brief="Purges a channel's messages",
        description="Purges the current channel's messages based on author criteria",
        usage="@user @another-user ... [number-to-purge (50 by default)]",
    )
    async def purge_x(
        self, ctx, targets: commands.Greedy[discord.Member], amount: int = 50
    ):
        # dat constant lookup
        targets = (
            set(user.id for user in ctx.message.mentions)
            if ctx.message.mentions
            else None
        )

        if amount <= 0 or amount > 50:
            amount = 50

        def check(message):
            if not targets or message.author.id in targets:
                return True
            return False

        try:
            await ctx.channel.purge(limit=amount, check=check)
            await self.bot.h.tagged_response(
                ctx,
                f"I finished deleting {amount} messages",
            )
        except discord.Forbidden:
            await self.bot.h.tagged_response(ctx, "I am not allowed to delete messages")
