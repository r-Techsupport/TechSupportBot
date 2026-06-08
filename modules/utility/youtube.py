"""Module for the google extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import munch
from discord import app_commands

import ui
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Youtube plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """
    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.google:
            raise AttributeError(
                "YoutubeSearcher was not loaded due to missing API key"
            )
    except AttributeError as exc:
        raise AttributeError(
            "YoutubeSearcher was not loaded due to missing API key"
        ) from exc

    await bot.add_cog(YoutubeSearcher(bot=bot))


class YoutubeSearcher(cogs.BaseCog):
    """Class for the google extension for the discord bot.

    Attributes:
        YOUTUBE_URL (str): The API URL for youtube search
    """

    YOUTUBE_URL: str = (
        "https://www.googleapis.com/youtube/v3/search?part=id&maxResults=10"
    )

    async def get_items(
        self: Self, url: str, data: dict[str, str]
    ) -> list[munch.Munch]:
        """Calls the google API and retuns only the relevant section from the response

        Args:
            url (str): The URL to query, either GOOGLE to YOUTUBE
            data (dict[str, str]): The parameters required by the google API

        Returns:
            list[munch.Munch]: The formatted list of items, ready to be processed and printed
        """
        response = await self.bot.http_functions.http_call(
            "get", url, params=data, use_cache=True
        )
        return response.get("items")

    @app_commands.command(
        name="youtube",
        description="Returns the top YouTube search result",
    )
    async def youtube(self: Self, interaction: discord.Interaction, query: str) -> None:
        """The entry point for the youtube search command

        Args:
            interaction (discord.Interaction): The context in which the command was run in
            query (str): The user inputted string to query google for
        """
        await interaction.response.defer()
        items = await self.get_items(
            self.YOUTUBE_URL,
            data={
                "q": query,
                "key": self.bot.file_config.api.api_keys.google,
                "type": "video",
            },
        )

        if not items:
            embed = auxiliary.prepare_deny_embed(
                f"No video results found for: *{query}*"
            )
            await interaction.followup.send(embed=embed)
            return

        video_id = items[0].get("id", {}).get("videoId")
        link = f"http://youtu.be/{video_id}"

        links = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            link = f"http://youtu.be/{video_id}" if video_id else None
            if link:
                links.append(link)

        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, links, interaction)
