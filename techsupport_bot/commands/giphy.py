"""Module for giphy extension in the bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import ui
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Giphy plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.giphy:
            raise AttributeError("Giphy was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("Giphy was not loaded due to missing API key") from exc

    await bot.add_cog(Giphy(bot=bot))


class Giphy(cogs.BaseCog):
    """Class for the giphy extension."""

    GIPHY_URL = "http://api.giphy.com/v1/gifs/search?q={}&api_key={}&limit={}"
    SEARCH_LIMIT = 10

    @staticmethod
    def parse_url(url: str) -> str:
        """Parses the raw API url into a useable gif link

        Args:
            url (str): The raw URL from Giphy

        Returns:
            str: The direct link to the gif, if it exists
        """
        index = url.find("?cid=")
        return url[:index]

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.command(
        name="giphy",
        brief="Grabs a random Giphy image",
        description="Grabs a random Giphy image based on your search",
        usage="[query]",
    )
    async def giphy(self: Self, ctx: commands.Context, *, query: str) -> None:
        """The main entry point and logic for the giphy command

        Args:
            ctx (commands.Context): The context in which the command was run
            query (str): The string to query the giphy API for
        """
        response = await self.bot.http_functions.http_call(
            "get",
            self.GIPHY_URL.format(
                query.replace(" ", "+"),
                self.bot.file_config.api.api_keys.giphy,
                self.SEARCH_LIMIT,
            ),
        )

        data = response.get("data")
        if not data:
            await auxiliary.send_deny_embed(
                message=f"No search results found for: *{query}*", channel=ctx.channel
            )
            return

        embeds = []
        for item in data:
            url = item.get("images", {}).get("original", {}).get("url")
            url = self.parse_url(url)
            embeds.append(url)

        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)
