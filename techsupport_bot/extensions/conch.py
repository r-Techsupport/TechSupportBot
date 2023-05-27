"""Module for the conch command in discord bot."""
import random

import base
import discord
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add conch to the config in discord bot."""
    await bot.add_cog(MagicConch(bot=bot))


class MagicConch(base.BaseCog):
    """Class to create the conch command for discord bot."""

    RESPONSES = [
        "As I see it, yes.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don’t count on it.",
        "It is certain.",
        "It is decidedly so.",
        "Most likely.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Outlook good.",
        "Reply hazy, try again.",
        "Signs point to yes.",
        "Very doubtful.",
        "Without a doubt.",
        "Yes.",
        "Yes – definitely.",
        "You may rely on it.",
    ]
    PIC_URL = "https://i.imgur.com/vdvGrsR.png"

    def format_question(self, question: str) -> str:
        question = question[:255]
        if not question.endswith("?"):
            question += "?"
        return question

    @commands.command(
        name="conch",
        aliases=["8ball", "8b"],
        brief="Asks the Magic Conch",
        description="Asks the Magic Conch (8ball) a question",
        usage="[question]",
    )
    async def ask_question(self, ctx, *, question: commands.clean_content() = None):
        """Method for how the conch command works for the bot."""
        # we don't actually care about the question

        if question == None:
            await ctx.send_deny_embed("You need to add a question")
            return
        formatted_question = self.format_question(question)
        embed = auxiliary.generate_basic_embed(
            title=formatted_question,
            description=random.choice(self.RESPONSES),
            color=discord.Color.blurple(),
            url=self.PIC_URL,
        )
        await ctx.send(embed=embed)
