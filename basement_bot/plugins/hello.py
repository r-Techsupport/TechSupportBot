from discord.ext import commands

from utils.helpers import tagged_response


def setup(bot):
    bot.add_command(hello)


@commands.command(
    name="hello",
    brief="Hello!",
    description="Returns the greeting 'Hello!' in a mention to the user sending the command.",
    usage="",
    help=(
        "\nLimitations: The bot will always only mention the user sending the command and"
        " ignores all other mentions or plain text in the message."
    ),
)
async def hello(ctx):
    await tagged_response(ctx, "Hello!")
