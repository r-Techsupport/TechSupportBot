"""Module for the animal extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the animals plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

    await bot.add_cog(Animals(bot=bot))


class Animals(cogs.BaseCog):
    """The class for the animals commands

    Attrs:
        CAT_API_URL (str): The URL for the cat API
        DOG_API_URL (str): The URL for the dog API
        FOX_API_URL (str): The URL for the fox API
        FROG_API_URL (str): The URL for the frog API
    """

    CAT_API_URL = "https://api.thecatapi.com/v1/images/search?limit=1&api_key={}"
    DOG_API_URL = "https://dog.ceo/api/breeds/image/random"
    FOX_API_URL = "https://randomfox.ca/floof/"
    FROG_API_URL = "https://frogs.media/api/random"

    @auxiliary.with_typing
    @commands.command(name="cat", brief="Gets a cat", description="Gets a cat")
    async def cat(self: Self, ctx: commands.Context) -> None:
        """Prints a cat to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        if not self.bot.file_config.api.api_keys.cat:
            embed = auxiliary.prepare_deny_embed(
                "No cat API has been set, so not cat can be shown"
            )
            await ctx.send(embed=embed)
            return

        url = self.CAT_API_URL.format(
            self.bot.file_config.api.api_keys.cat,
        )
        response = await self.bot.http_functions.http_call("get", url)
        await ctx.send(response[0].url)

    @auxiliary.with_typing
    @commands.command(name="dog", brief="Gets a dog", description="Gets a dog")
    async def dog(self: Self, ctx: commands.Context) -> None:
        """Prints a dog to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.DOG_API_URL)
        await ctx.send(response.message)

    @auxiliary.with_typing
    @commands.command(name="frog", brief="Gets a frog", description="Gets a frog")
    async def frog(self: Self, ctx: commands.Context) -> None:
        """Prints a frog to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.FROG_API_URL)
        await ctx.send(response.url)

    @auxiliary.with_typing
    @commands.command(name="fox", brief="Gets a fox", description="Gets a fox")
    async def fox(self: Self, ctx: commands.Context) -> None:
        """Prints a fox to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.FOX_API_URL)
        await ctx.send(response.image)
