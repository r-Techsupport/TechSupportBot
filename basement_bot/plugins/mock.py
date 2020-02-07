import logging

from discord.ext import commands

from utils.helpers import get_env_value, priv_response, tagged_response

COMMAND_PREFIX = get_env_value("COMMAND_PREFIX")
SEARCH_LIMIT = 50


def setup(bot):
    bot.add_command(mock)


def mock_string(string):
    mock = ""
    i = True
    for char in string:
        if i:
            mock += char.upper()
        else:
            mock += char.lower()
        if char != " ":
            i = not i
    return mock


@commands.command(
    name="sb",
    brief="MOcKS last MeSSAgE Of MeNtIONeD uSEr A LA moCkiNg SpONgEBob MeME",
    description=(
        "Returns last message of mentioned user following command changing"
        " random characters to capital or lowercase."
    ),
    usage="[mentioned-user]",
    help=(
        "\nLimitations: Ignores any additional mentions after the command"
        " and first mentioned user."
    ),
)
async def mock(ctx):
    user_to_mock = ctx.message.mentions[0] if ctx.message.mentions else None

    if not user_to_mock:
        await priv_response(ctx, "You must tag a user if you want to mock them!")
        return

    if user_to_mock.bot:
        user_to_mock = ctx.author

    mock_message = None
    async for message in ctx.channel.history(limit=SEARCH_LIMIT):
        if message.author == user_to_mock and not message.content.startswith(
            COMMAND_PREFIX
        ):
            mock_message = message.content
            break

    if not mock_message:
        await priv_response(ctx, f"No message found for user {user_to_mock}")
        return

    await tagged_response(ctx, mock_string(mock_message))
