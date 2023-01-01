import random

import base
import discord
import util
from discord.ext import commands


def setup(bot):
    bot.add_cog(Roller(bot=bot))


class RollEmbed(discord.Embed):

    ICON_URL = "https://cdn.icon-icons.com/icons2/1465/PNG/512/678gamedice_100992.png"

    def __init__(self, *args, **kwargs):
        roll = kwargs.pop("roll")
        super().__init__(*args, **kwargs)
        self.title = "RNG Roller"
        self.set_thumbnail(url=self.ICON_URL)
        self.description = f"You rolled a {roll}!"
        self.color = discord.Color.gold()


class Roller(base.BaseCog):
    @util.with_typing
    @commands.command(
        name="roll",
        brief="Rolls a number",
        description="Rolls a random number in a given range",
        usage="[minimum] [maximum] (defaults to 1-100)",
    )
    async def roll(self, ctx, min: int = 1, max: int = 100):
        embed = RollEmbed(roll=random.randint(min, max))
        await ctx.send(embed=embed)
