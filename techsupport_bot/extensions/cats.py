"""Module for the urban dictionary extension for the discord bot."""
import base
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Loading the Cats plugin"""

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.cat:
            raise AttributeError("Cats was not loaded due to missing API key")
    except AttributeError:
        raise AttributeError("Cats was not loaded due to missing API key")

    await bot.add_cog(Cats(bot=bot))


class Cats(base.BaseCog):
    """The class for the cat api"""

    API_URL = "https://api.thecatapi.com/v1/images/search?limit=1&api_key={}"

    @auxiliary.with_typing
    @commands.command(name="cat", brief="Gets a cat")
    async def cat(self, ctx):
        """Prints a cat to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        url = self.API_URL.format(
            self.bot.file_config.api.api_keys.cat,
        )
        response = await self.bot.http_call("get", url)
        await ctx.send(response[0].url)
