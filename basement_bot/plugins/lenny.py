import random

import base
import util
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[Lenny])


class Lenny(base.BaseCog):

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

    @util.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="len",
        brief="Returns a Lenny face",
        description="Returns a randomly chosen Lenny face ( ͡° ͜ʖ ͡°)",
    )
    async def lenny(self, ctx):
        await ctx.send(random.choice(self.LENNYS_SELECTION))
