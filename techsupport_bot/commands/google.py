"""Module for the google extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import munch
import ui
from core import auxiliary, cogs, extensionconfig
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Google plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """
    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.google:
            raise AttributeError("Googler was not loaded due to missing API key")
        if not bot.file_config.api.api_keys.google_cse:
            raise AttributeError("Googler was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("Googler was not loaded due to missing API key") from exc

    config = extensionconfig.ExtensionConfig()
    config.add(
        key="max_responses",
        datatype="int",
        title="Max Responses",
        description="The max amount of responses per embed page",
        default=1,
    )

    await bot.add_cog(Googler(bot=bot))
    bot.add_extension_config("google", config)


def build_google_search_params(
    cse_key: str, api_key: str, query: str
) -> dict[str, str]:
    """Builds request params for google web search.

    Args:
        cse_key (str): Google custom search engine key
        api_key (str): Google API key
        query (str): Search query

    Returns:
        dict[str, str]: Prepared parameters for the Google search API
    """
    return {"cx": cse_key, "q": query, "key": api_key}


def build_google_image_params(cse_key: str, api_key: str, query: str) -> dict[str, str]:
    """Builds request params for google image search.

    Args:
        cse_key (str): Google custom search engine key
        api_key (str): Google API key
        query (str): Search query

    Returns:
        dict[str, str]: Prepared parameters for the Google image API
    """
    params = build_google_search_params(cse_key, api_key, query)
    params["searchType"] = "image"
    return params


def build_youtube_params(api_key: str, query: str) -> dict[str, str]:
    """Builds request params for youtube search.

    Args:
        api_key (str): Google API key
        query (str): Search query

    Returns:
        dict[str, str]: Prepared parameters for the YouTube search API
    """
    return {"q": query, "key": api_key, "type": "video"}


def extract_google_search_fields(
    items: list[munch.Munch], query: str
) -> list[tuple[str, str]]:
    """Extracts link/snippet field data from Google search items.

    Args:
        items (list[munch.Munch]): Search response items from Google API
        query (str): The original query for fallback values

    Returns:
        list[tuple[str, str]]: Tuple list of link/snippet field values
    """
    fields = []
    for item in items:
        link = item.get("link")
        if not link:
            continue
        snippet = item.get("snippet", f"No details available for {query}")
        cleaned_snippet = snippet.replace("\n", "")
        fields.append((link, cleaned_snippet))

    return fields


def chunk_search_fields(
    fields: list[tuple[str, str]], max_per_page: int
) -> list[list[tuple[str, str]]]:
    """Splits search field tuples into embed-sized chunks.

    Args:
        fields (list[tuple[str, str]]): Link/snippet tuple list
        max_per_page (int): Maximum number of fields per chunk

    Returns:
        list[list[tuple[str, str]]]: Chunked fields for paginated embeds
    """
    chunks = []
    normalized_max = max(1, max_per_page)
    current_chunk = []

    for field in fields:
        current_chunk.append(field)
        if len(current_chunk) == normalized_max:
            chunks.append(current_chunk)
            current_chunk = []

    if len(current_chunk) > 0:
        chunks.append(current_chunk)

    return chunks


def extract_image_links(items: list[munch.Munch]) -> list[str]:
    """Extracts valid image links from Google image response items.

    Args:
        items (list[munch.Munch]): Image search response items

    Returns:
        list[str]: Valid image links
    """
    links = []
    for item in items:
        link = item.get("link")
        if not link:
            continue
        links.append(link)

    return links


def extract_youtube_links(items: list[munch.Munch]) -> list[str]:
    """Extracts valid youtube links from YouTube response items.

    Args:
        items (list[munch.Munch]): YouTube search response items

    Returns:
        list[str]: Valid youtube links built from video IDs
    """
    links = []
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        if not video_id:
            continue
        links.append(f"http://youtu.be/{video_id}")

    return links


def build_no_results_message(kind: str, query: str) -> str:
    """Builds no-result messages based on search kind.

    Args:
        kind (str): Search type, one of search/image/video
        query (str): Original query

    Returns:
        str: User-facing no-result message
    """
    if kind == "image":
        return f"No image search results found for: *{query}*"
    if kind == "video":
        return f"No video results found for: *{query}*"
    return f"No search results found for: *{query}*"


def build_google_parse_error_message() -> str:
    """Builds a standardized parsing failure message.

    Returns:
        str: User-facing parse error message
    """
    return "I had an issue processing Google's response... try again later!"


class Googler(cogs.BaseCog):
    """Class for the google extension for the discord bot.

    Attributes:
        GOOGLE_URL (str): The API URL for google search
        YOUTUBE_URL (str): The API URL for youtube search
        ICON_URL (str): The google icon
    """

    GOOGLE_URL: str = "https://www.googleapis.com/customsearch/v1"
    YOUTUBE_URL: str = (
        "https://www.googleapis.com/youtube/v3/search?part=id&maxResults=10"
    )
    ICON_URL: str = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/"
        + "c1/Google_%22G%22_logo.svg/768px-Google_%22G%22_logo.svg.png"
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
        return response.get("items", [])

    google_group: app_commands.Group = app_commands.Group(
        name="google",
        description="Command Group for Google Search",
        extras={"module": "google"},
    )

    @google_group.command(
        name="search",
        description="Returns the top Google search result",
        extras={"module": "google"},
    )
    async def search(self: Self, interaction: discord.Interaction, query: str) -> None:
        """The entry point for the URL search command

        Args:
            interaction (discord.Interaction): The interaction in which the command was run in
            query (str): The user inputted string to query google for
        """
        await interaction.response.defer(ephemeral=False)
        data = build_google_search_params(
            cse_key=self.bot.file_config.api.api_keys.google_cse,
            api_key=self.bot.file_config.api.api_keys.google,
            query=query,
        )

        items = await self.get_items(self.GOOGLE_URL, data)

        if not items:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    build_no_results_message("search", query)
                ),
                ephemeral=True,
            )
            return

        config = self.bot.guild_configs[str(interaction.guild.id)]
        fields = extract_google_search_fields(items, query)
        if not fields:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(build_google_parse_error_message()),
                ephemeral=True,
            )
            return

        chunks = chunk_search_fields(
            fields, config.extensions.google.max_responses.value
        )
        embeds = []
        for chunk in chunks:
            embed = auxiliary.generate_basic_embed(
                title=f"Results for {query}", url=self.ICON_URL
            )
            for link, snippet in chunk:
                embed.add_field(name=link, value=snippet, inline=False)
            embeds.append(embed)

        await ui.PaginateView().send(
            interaction.channel, interaction.user, embeds, interaction
        )

    @google_group.command(
        name="images",
        description="Returns the top Google Images search result",
        extras={"module": "google"},
    )
    async def images(self: Self, interaction: discord.Interaction, query: str) -> None:
        """The entry point for the image search command

        Args:
            interaction (discord.Interaction): The interaction in which the command was run in
            query (str): The user inputted string to query google for
        """
        await interaction.response.defer(ephemeral=False)
        data = build_google_image_params(
            cse_key=self.bot.file_config.api.api_keys.google_cse,
            api_key=self.bot.file_config.api.api_keys.google,
            query=query,
        )
        items = await self.get_items(self.GOOGLE_URL, data)

        if not items:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    build_no_results_message("image", query)
                ),
                ephemeral=True,
            )
            return

        links = extract_image_links(items)
        if not links:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(build_google_parse_error_message()),
                ephemeral=True,
            )
            return

        await ui.PaginateView().send(
            interaction.channel, interaction.user, links, interaction
        )

    @app_commands.command(
        name="youtube",
        description="Returns the top YouTube search result",
        extras={"module": "google"},
    )
    async def youtube(self: Self, interaction: discord.Interaction, query: str) -> None:
        """The entry point for the youtube search command

        Args:
            interaction (discord.Interaction): The interaction in which the command was run in
            query (str): The user inputted string to query google for
        """
        await interaction.response.defer(ephemeral=False)
        items = await self.get_items(
            self.YOUTUBE_URL,
            data=build_youtube_params(self.bot.file_config.api.api_keys.google, query),
        )

        if not items:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    build_no_results_message("video", query)
                ),
                ephemeral=True,
            )
            return

        links = extract_youtube_links(items)
        if not links:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(build_google_parse_error_message()),
                ephemeral=True,
            )
            return

        await ui.PaginateView().send(
            interaction.channel, interaction.user, links, interaction
        )
