import random

import base
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[MagicConch])


class MagicConch(base.BaseCog):

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

    @commands.command(
        name="conch",
        aliases=["8ball", "8b"],
        brief="Asks the Magic Conch",
        description="Asks the Magic Conch (8ball) a question",
    )
    async def ask_question(self, ctx, *, question: str):
        # we don't actually care about the question
        response = random.choice(self.RESPONSES)
        if not question.endswith("?"):
            question += "?"

        question = self.bot.sub_mentions_for_usernames(question)

        embed = discord.Embed(title=question, description=response)

        embed.set_thumbnail(url=self.PIC_URL)

        await self.bot.send_with_mention(ctx, embed=embed)
