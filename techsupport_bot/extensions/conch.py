"""Module for the conch command in discord bot."""
import random

import base
import discord
from discord.ext import commands


def setup(bot):
    """Method to add conch to the config in discord bot."""
    bot.add_cog(MagicConch(bot=bot))


class ConchEmbed(discord.Embed):
    """Class to create the conch embed for the bot."""

    PIC_URL = "https://i.imgur.com/vdvGrsR.png"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_thumbnail(url=self.PIC_URL)
        self.color = discord.Color.blurple()


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
        response = random.choice(self.RESPONSES)
        if question == None:
            await ctx.send_deny_embed("You need to add a question")
            return
        if not question.endswith("?"):
            question += "?"

        embed = ConchEmbed(title=question[:256], description=response)
        await ctx.send(embed=embed)
