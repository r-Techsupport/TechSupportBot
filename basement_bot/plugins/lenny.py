from random import choice

from cogs import BasicPlugin
from discord.ext import commands
from helper import with_typing


def setup(bot):
    bot.add_cog(Lenny(bot))


class Lenny(BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False

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
        "(▀̿Ĺ̯▀̿ ̿)",
        "( ͡~ ͜ʖ ͡°)",
        "✺◟( ͡° ͜ʖ ͡°)◞✺",
    ]

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="len",
        brief="( ͡° ͜ʖ ͡°)",
        description="Returns a randomly chosen Lenny face.",
        usage="",
        help="\nLimitations: Ignores any plain text or mentions after the command.",
    )
    async def lenny(self, ctx):
        await ctx.send(choice(self.LENNYS_SELECTION))
