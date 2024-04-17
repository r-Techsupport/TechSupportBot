"""Module for the wolfram extension for the discord bot."""

import discord
from core import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Adding the wolfram configuration to the config file."""

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.wolfram:
            raise AttributeError("Wolfram was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("Wolfram was not loaded due to missing API key") from exc

    await bot.add_cog(Wolfram(bot=bot))


class Wolfram(cogs.BaseCog):
    """Class to set up the wolfram extension."""

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
    async def simple_search(self, ctx, *, query: str):
        """Method to search through the wolfram API."""
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
