"""Module to add the extension lenny to the discord bot."""
import random

import base
import discord
import util
from discord.ext import commands


async def setup(bot):
    """Adding lenny to the config file."""
    await bot.add_cog(Lenny(bot=bot))


class Lenny(base.BaseCog):
    """Class for lenny extension."""

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
    @commands.command(
        name="len",
        brief="Returns a Lenny face",
        description="Returns a randomly chosen Lenny face ( ͡° ͜ʖ ͡°)",
    )
    async def lenny(self, ctx: commands.Context):
        """Method for a discord command to return a funny lenny face.

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        await self.lenny_command(ctx.channel)

    async def lenny_command(self, channel: discord.abc.Messageable):
        """The main logic for the lenny command

        Args:
            channel (discord.abc.Messageable): The channel where the lenny command was called in
        """
        await channel.send(content=random.choice(self.LENNYS_SELECTION))
