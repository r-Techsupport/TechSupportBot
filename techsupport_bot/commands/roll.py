"""Module for the roll extension for the discord bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Roll plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Roller(bot=bot))


class Roller(cogs.BaseCog):
    """Class for the roll command for the extension.

    Attrs:
        ICON_URL (str): The URL for the dice icon

    """

    ICON_URL = "https://cdn.icon-icons.com/icons2/1465/PNG/512/678gamedice_100992.png"

    @auxiliary.with_typing
    @commands.command(
        name="roll",
        brief="Rolls a number",
        description="Rolls a random number in a given range",
        usage="[minimum] [maximum] (defaults to 1-100)",
    )
    async def roll(
        self: Self, ctx: commands.Context, min_value: int = 1, max_value: int = 100
    ) -> None:
        """The function that is called when .roll is run on discord

        Args:
            ctx (commands.Context): The context in which the command was run in
            min_value (int, optional): The mininum value of the dice. Defaults to 1.
            max_value (int, optional): The maximum value of the dice. Defaults to 100.
        """
        await self.roll_command(ctx=ctx, min_value=min_value, max_value=max_value)

    async def roll_command(
        self: Self, ctx: commands.Context, min_value: int, max_value: int
    ) -> None:
        """The core logic for the roll command

        Args:
            ctx (commands.Context): The context in which the command was run in
            min_value (int, optional): The mininum value of the dice.
            max_value (int, optional): The maximum value of the dice.
        """
        number = self.get_roll_number(min_value=min_value, max_value=max_value)
        embed = auxiliary.generate_basic_embed(
            title="RNG Roller",
            description=f"You rolled a {number}",
            color=discord.Color.gold(),
            url=self.ICON_URL,
        )
        await ctx.send(embed=embed)

    def get_roll_number(self: Self, min_value: int, max_value: int) -> int:
        """A function to get a random number based on min and max values

        Args:
            min_value (int, optional): The mininum value of the dice.
            max_value (int, optional): The maximum value of the dice.

        Returns:
            int: The random number
        """
        return random.randint(min_value, max_value)
