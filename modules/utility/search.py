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
    """Loading the Search Engine plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """
    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.tavily:
            raise AttributeError("WebSearcher was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError(
            "WebSearcher was not loaded due to missing API key"
        ) from exc

    await bot.add_cog(WebSearcher(bot=bot))


class WebSearcher(cogs.BaseCog):
    """Class for the google extension for the discord bot.

    Attributes:
        search (app_commands.Group): The group for the /search commands
    """

    search: app_commands.Group = app_commands.Group(
        name="search", description="Command Group for the Search Extension"
    )

    async def make_request(self: Self, query: str) -> munch.Munch:
        """This functions make a request to the Tavily API
        This pulls the API key from the config and returns a munch.Munch result

        Args:
            query (str): The string query passed in by the user

        Returns:
            munch.Munch: The result from the tavily API
        """
        api_url: str = "https://api.tavily.com/search"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bot.file_config.api.api_keys.tavily}",
        }
        json_data = {
            "query": query,
            "search_depth": "advanced",
            "include_images": "true",
        }
        response = await self.bot.http_functions.http_call(
            "post",
            api_url,
            headers=headers,
            json=json_data,
        )

        return response

    @search.command(
        name="text",
        description="Returns the top Web search result",
    )
    async def websearch_text(
        self: Self, interaction: discord.Interaction, query: str
    ) -> None:
        """This is the command for plaintext searches

        Args:
            interaction (discord.Interaction): The interaction that called the command
            query (str): The string query passed in by the user
        """
        await interaction.response.defer()
        response = await self.make_request(query)

        embeds = []

        for result in response.results[:10]:
            embed = discord.Embed(
                title=f"Search results for {query}", description=result.url
            )
            embed.add_field(
                name=result.title[:100],
                value=result.content[:100],
            )
            embed.color = discord.Color.blurple()
            embeds.append(embed)

        if not embeds:
            embed = auxiliary.prepare_deny_embed(f"No results returned for {query}")
            await interaction.followup.send(embed=embed)

        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)

    @search.command(
        name="images",
        description="Returns the top Web search image result",
    )
    async def websearch_image(
        self: Self, interaction: discord.Interaction, query: str
    ) -> None:
        """This is the command for image searches

        Args:
            interaction (discord.Interaction): The interaction that called the command
            query (str): The string query passed in by the user
        """
        await interaction.response.defer()
        response = await self.make_request(query)

        embeds = []

        for result in response.images[:10]:
            embed = discord.Embed(title=f"Search results for {query}")
            embed.set_image(url=result)
            embed.color = discord.Color.blurple()
            embeds.append(embed)

        if not embeds:
            embed = auxiliary.prepare_deny_embed(f"No results returned for {query}")
            await interaction.followup.send(embed=embed)

        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)
