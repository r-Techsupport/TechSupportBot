from random import choice

from discord.ext import commands

from cogs import BasicPlugin


def setup(bot):
    bot.add_cog(Lenny(bot))


class Lenny(BasicPlugin):

    LENNYS_SELECTION = [
        "( ͡° ͜ʖ ͡°)",
        "( ͠° ͟ʖ ͡°)",
        "( ͡ʘ ͜ʖ ͡ʘ)",
        "(° ͜ʖ °)",
        "ಠ_ಠ",
        "( ͡°( ͡° ͜ʖ( ͡° ͜ʖ ͡°)ʖ ͡°) ͡°)",
        "༼  ͡° ͜ʖ ͡° ༽",
        "(͡ ͡° ͜ つ ͡͡°)",
        "[̲̅$̲̅(̲̅ ͡° ͜ʖ ͡°̲̅)̲̅$̲̅]",
        "( ͡o ͜ʖ ͡o)",
        "(⟃ ͜ʖ ⟄)",
        "( ͜。 ͡ʖ ͜。)",
        "( ͡°⊖ ͡°)",
        "✧･ﾟ: *✧･ﾟ♡*( ͡˘̴ ͜ ʖ̫ ͡˘̴ )*♡･ﾟ✧*:･ﾟ✧",
        "°。°。°。°( ͡° ͜ʖ ͡ °)°。°。°。°",
        "┐( ͡ಠ ʖ̯ ͡ಠ)┌",
        "ʕ ͡° ʖ̯ ͡°ʔ",
        "╭∩╮( ͡° ل͟ ͡° )╭∩╮",
    ]

    @commands.command(
        name="len",
        brief="( ͡° ͜ʖ ͡°)",
        description="Returns a randomly chosen Lenny face.",
        usage="",
        help="\nLimitations: Ignores any plain text or mentions after the command.",
    )
    async def lenny(self, ctx):
        await ctx.send(choice(self.LENNYS_SELECTION))
