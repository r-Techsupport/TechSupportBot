"""Module for the dog extension for the discord bot."""

from core import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Loading the Dog plugin"""
    await bot.add_cog(Dogs(bot=bot))


class Dogs(cogs.BaseCog):
    """The class for the dog api"""

    API_URL = "https://dog.ceo/api/breeds/image/random"

    @auxiliary.with_typing
    @commands.command(name="dog", brief="Gets a dog")
    async def dog(self, ctx):
        """Prints a dog to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.API_URL)
        print(f"Response {response}")
        await ctx.send(response.message)
