from random import choice

from discord.ext import commands


def setup(bot):
    bot.add_command(lenny)


@commands.command(
    name="len",
    brief="( ͡° ͜ʖ ͡°)",
    description="Returns a randomly chosen Lenny face.",
    usage="",
    help="\nLimitations: Ignores any plain text or mentions after the command.",
)
async def lenny(ctx):
    await ctx.send(choice(lennys))


lennys = [
    "( ͡° ͜ʖ ͡°)",
    "( ͠° ͟ʖ ͡°)",
    "( ͡ʘ ͜ʖ ͡ʘ)",
    "(° ͜ʖ °)",
    "ಠ_ಠ",
    "( ͡°( ͡° ͜ʖ( ͡° ͜ʖ ͡°)ʖ ͡°) ͡°)",
    "༼  ͡° ͜ʖ ͡° ༽",
    "(͡ ͡° ͜ つ ͡͡°)",
    "[̲̅$̲̅(̲̅ ͡° ͜ʖ ͡°̲̅)̲̅$̲̅]",
]
