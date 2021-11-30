import random

import base
import util
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[Roller])


class Roller(base.BaseCog):
    @commands.command(
        name="roll",
        brief="Rolls a number",
        description="Rolls a random number in a given range",
        usage="[minimum] [maximum] (defaults to 1-100)",
    )
    async def roll(self, ctx, min: int = 1, max: int = 100):
        result = random.randint(min, max)
        await util.send_with_mention(ctx, result)
