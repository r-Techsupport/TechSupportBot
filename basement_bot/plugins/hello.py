import base
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[Greeter])


class Greeter(base.BaseCog):
    @commands.command(
        name="hello",
        brief="Says hello to the bot",
        description="Says hello to the bot (because they are doing such a great job!)",
        usage="",
    )
    async def hello(self, ctx):
        # H, E, Y
        emojis = ["🇭", "🇪", "🇾"]
        for emoji in emojis:
            await ctx.message.add_reaction(emoji)
