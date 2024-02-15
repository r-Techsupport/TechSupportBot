"""Module for the animal extension for the discord bot."""

from core import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Loading the animal plugin"""

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.cat:
            raise AttributeError("Cats was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("Cats was not loaded due to missing API key") from exc

    await bot.add_cog(Cats(bot=bot))
    await bot.add_cog(Dogs(bot=bot))
    await bot.add_cog(Frogs(bot=bot))
    await bot.add_cog(Fox(bot=bot))


class Cats(cogs.BaseCog):
    """The class for the cat api"""

    API_URL = "https://api.thecatapi.com/v1/images/search?limit=1&api_key={}"

    @auxiliary.with_typing
    @commands.command(name="cat", brief="Gets a cat", description="Gets a cat")
    async def cat(self, ctx):
        """Prints a cat to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        url = self.API_URL.format(
            self.bot.file_config.api.api_keys.cat,
        )
        response = await self.bot.http_functions.http_call("get", url)
        await ctx.send(response[0].url)


class Dogs(cogs.BaseCog):
    """The class for the dog api"""

    API_URL = "https://dog.ceo/api/breeds/image/random"

    @auxiliary.with_typing
    @commands.command(name="dog", brief="Gets a dog", description="Gets a dog")
    async def dog(self, ctx: commands.Context):
        """Prints a dog to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.API_URL)
        await ctx.send(response.message)


class Frogs(cogs.BaseCog):
    """The class for the frog api"""

    API_BASE_URL = "https://frogs.media/api/random"

    @auxiliary.with_typing
    @commands.command(name="frog", brief="Gets a frog", description="Gets a frog")
    async def frog(self, ctx: commands.Context):
        """Prints a frog to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.API_BASE_URL)
        await ctx.send(response.url)


class Fox(cogs.BaseCog):
    """The class for the fox api"""

    API_BASE_URL = "https://randomfox.ca/floof/"

    @auxiliary.with_typing
    @commands.command(name="fox", brief="Gets a fox", description="Gets a fox")
    async def fox(self, ctx: commands.Context):
        """Prints a fox to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.API_BASE_URL)
        print(f"Response: {response}")
        await ctx.send(response.image)
