"""Module to add the extension lenny to the discord bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Lenny plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Lenny(bot=bot))


class Lenny(cogs.BaseCog):
    """Class for lenny extension.

    Attrs:
        LENNYS_SELECTION (list[str]): The list of lenny faces to pick one randomly

    """

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

    @auxiliary.with_typing
    @commands.command(
        name="len",
        brief="Returns a Lenny face",
        description="Returns a randomly chosen Lenny face ( ͡° ͜ʖ ͡°)",
    )
    async def lenny(self: Self, ctx: commands.Context) -> None:
        """Method for a discord command to return a funny lenny face.

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        await self.lenny_command(ctx.channel)

    async def lenny_command(self: Self, channel: discord.abc.Messageable) -> None:
        """The main logic for the lenny command

        Args:
            channel (discord.abc.Messageable): The channel where the lenny command was called in
        """
        await channel.send(content=random.choice(self.LENNYS_SELECTION))
