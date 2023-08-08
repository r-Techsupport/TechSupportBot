"""Module for the wyr extension for the discord bot."""
import random

import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Adding the would you rather configuration to the config file."""
    await bot.add_cog(WouldYouRather(bot=bot))


class WouldYouRather(base.BaseCog):
    """Class to create a would you rather scenario."""

    async def preconfig(self):
        """Method to preconfig the wyr scenario."""
        self.last = None

    @util.with_typing
    @commands.command(
        name="wyr",
        brief="Gets Would You Rather questions",
        description="Creates a random Would You Rather question",
    )
    async def wyr_command(self, ctx: commands.Context) -> None:
        """The main processing of .wyr

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        question = self.get_question()
        embed = auxiliary.generate_basic_embed(
            title="Would you rather...",
            description=str(question),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    def get_question(self) -> str:
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
            return selection.strip('"').replace('" || "', ", ").capitalize()
