from discord.ext import commands

from cogs import BasicPlugin
from utils.helpers import emoji_reaction


def setup(bot):
    bot.add_cog(Greeter(bot))


class Greeter(BasicPlugin):
    @commands.command(
        name="hello",
        brief="Hello!",
        description="Returns the greeting 'HEY' as a reaction to the original command message.",
        usage="",
    )
    async def hello(self, ctx):
        # H, E, Y
        emojis = [u"\U0001F1ED", u"\U0001F1EA", u"\U0001F1FE"]
        await emoji_reaction(ctx, emojis)
