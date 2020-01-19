import logging

from discord.ext import commands


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


@commands.command(name="sb")
async def mock(ctx):
    user_to_mock = ctx.message.mentions or None

    if not user_to_mock:
        await ctx.send(f"You must tag a user if you want to mock them!")
        return

    mock_message = None
    async for message in ctx.channel.history(limit=200, oldest_first=True):
        if message.author == user_to_mock[0] and not message.content.startswith("."):
            mock_message = message.content

    if not mock_message:
        await ctx.send(f"No message found for user {user_to_mock[0]}")
        return

    await ctx.send(mock_string(mock_message))
