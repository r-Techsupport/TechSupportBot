from discord.ext import commands


def setup(bot):
    bot.add_command(hello)


@commands.command(name="hello")
async def hello(ctx):
    await ctx.send("Hello to you!")
