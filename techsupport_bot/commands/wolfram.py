"""Module for the wolfram extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Wolfram Alpha plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.wolfram:
            raise AttributeError("Wolfram was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("Wolfram was not loaded due to missing API key") from exc

    await bot.add_cog(Wolfram(bot=bot))


class Wolfram(cogs.BaseCog):
    """Class to set up the wolfram extension.

    Attrs:
        API_URL (str): The API URL for wolfram
        ICON_URL (str): The URL for the wolfram icon

    """

    API_URL = "http://api.wolframalpha.com/v1/result?appid={}&i={}"
    ICON_URL = "https://cdn.icon-icons.com/icons2/2107/PNG/512/file_type_wolfram_icon_130071.png"

    @auxiliary.with_typing
    @commands.command(
        name="wa",
        aliases=["math", "wolframalpha", "jarvis"],
        brief="Searches Wolfram Alpha",
        description="Searches the simple answer Wolfram Alpha API",
        usage="[query]",
    )
    async def simple_search(self: Self, ctx: commands.Context, *, query: str) -> None:
        """Makes a search on wolframalpha for the user input query

        Args:
            ctx (commands.Context): The context which generated the command
            query (str): The user inputed query to search wolfram for and output the results
        """
        url = self.API_URL.format(
            self.bot.file_config.api.api_keys.wolfram,
            query,
        )

        response = await self.bot.http_functions.http_call(
            "get", url, get_raw_response=True
        )
        if response["status"] == 501:
            await auxiliary.send_deny_embed(
                message="Wolfram|Alpha did not like that question", channel=ctx.channel
            )
            return
        if response["status"] != 200:
            await auxiliary.send_deny_embed(
                message="Wolfram|Alpha ran into an error", channel=ctx.channel
            )
            return

        answer = response["text"]
        embed = auxiliary.generate_basic_embed(
            description=answer, color=discord.Color.orange(), url=self.ICON_URL
        )
        await ctx.send(embed=embed)
