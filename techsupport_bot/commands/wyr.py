"""Module for the wyr extension for the discord bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the WYR plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(WouldYouRather(bot=bot))


class WouldYouRather(cogs.BaseCog):
    """Class to create a would you rather scenario."""

    async def preconfig(self: Self) -> None:
        """Method to preconfig the wyr scenario."""
        self.last = None

    @auxiliary.with_typing
    @commands.command(
        name="wyr",
        brief="Gets Would You Rather questions",
        description="Creates a random Would You Rather question",
    )
    async def wyr(self: Self, ctx: commands.Context) -> None:
        """Exists to preserve undecorated wyr_command for testing

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        await self.wyr_command(ctx)

    async def wyr_command(self: Self, ctx: commands.Context) -> None:
        """The main processing of .wyr

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        question = self.get_question()
        embed = auxiliary.generate_basic_embed(
            title="Would you rather...",
            description=self.create_question_string(question),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    def get_question(self: Self) -> str:
        """This gets a non-repeated question

        Returns:
            str: The question to print to the user
        """
        with open(r"resources/wyrQuestions.txt", encoding="utf-8") as f:
            questions = f.read().splitlines()
            try:
                questions.remove(self.last)
            except ValueError:
                pass
            selection = random.choice(questions)
            self.last = selection
            return selection

    @staticmethod
    def create_question_string(question: str) -> str:
        """Converts a string in the form of
        '\"option1\" || \"option2\"' to
        'option1, or option2?'

        Args:
            question (str): resource string

        Returns:
            str: question string"""
        return question.strip('"').replace('" || "', ", or ").capitalize() + "?"
