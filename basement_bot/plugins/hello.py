import cogs
from discord.ext import commands


def setup(bot):
    bot.add_cog(Greeter(bot))


class Greeter(cogs.BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False

    @commands.command(
        name="hello",
        brief="Hello!",
        description="Returns the greeting 'HEY' as a reaction to the original command message.",
        usage="",
    )
    async def hello(self, ctx):
        # H, E, Y
        emojis = ["🇭", "🇪", "🇾"]
        await self.bot.h.emoji_reaction(ctx, emojis)
