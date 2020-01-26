from discord.ext import commands

from utils.helpers import tagged_response


def setup(bot):
    bot.add_command(hello)


@commands.command(name="hello")
async def hello(ctx):
    await tagged_response(ctx, "Hello!")
