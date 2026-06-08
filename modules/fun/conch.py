"""
Module for the conch command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Magic Conch plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(MagicConch(bot=bot))


class MagicConch(cogs.BaseCog):
    """Class to create the conch command for discord bot.

    Attributes:
        RESPONSES (list[str]): The list of random responses for the 8 ball
        PIC_URL (str): The direct URL for the picture to put in embeds

    """

    RESPONSES: list[str] = [
        "As I see it, yes.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don't count on it.",
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
        "Yes - definitely.",
        "You may rely on it.",
    ]
    PIC_URL: str = "https://i.imgur.com/vdvGrsR.png"

    @app_commands.command(
        name="conch",
        description="Asks the Magic Conch (8ball) a question",
    )
    async def conch_command(
        self: Self, interaction: discord.Interaction, question: str
    ) -> None:
        """Method for the core logic of the conch command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            question (str): The question asked.
        """
        formatted_question = format_question(question)
        embed = auxiliary.generate_basic_embed(
            title=formatted_question,
            description=random.choice(self.RESPONSES),
            color=discord.Color.blurple(),
            url=self.PIC_URL,
        )
        await interaction.response.send_message(embed=embed)


def format_question(question: str) -> str:
    """This formats a question properly. It will crop it if needed, and add a "?" to the end

    Args:
        question (str): The original question passed from the user

    Returns:
        str: The final formatted questions. Will always be 256 or less in length,
            and end with a "?"
    """
    question = question[:255]
    if not question.endswith("?"):
        question += "?"
    return question
