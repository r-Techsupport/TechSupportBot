"""Module for the hello extension for the bot."""
import base
from discord.ext import commands


def setup(bot):
    """Add the hello greeter to the config file."""
    bot.add_cog(Greeter(bot=bot))


class Greeter(base.BaseCog):
    """Class for the greeter command."""
    @commands.command(
        name="hello",
        brief="Says hello to the bot",
        description="Says hello to the bot (because they are doing such a great job!)",
        usage="",
    )
    async def hello(self, ctx):
        """Method to respond to hellos by the bot."""
        # H, E, Y
        emojis = ["🇭", "🇪", "🇾"]
        for emoji in emojis:
            await ctx.message.add_reaction(emoji)
