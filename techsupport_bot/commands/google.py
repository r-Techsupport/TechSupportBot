"""Module for the google extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import munch
import ui
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

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


class Googler(cogs.BaseCog):
    """Class for the google extension for the discord bot.

    Attrs:
        GOOGLE_URL (str): The API URL for google search
        YOUTUBE_URL (str): The API URL for youtube search
        ICON_URL (str): The google icon
    """

    GOOGLE_URL = "https://www.googleapis.com/customsearch/v1"
    YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/search?part=id&maxResults=10"
    ICON_URL = (
        "https://cdn.icon-icons.com/icons2/673/PNG/512/Google_icon-icons.com_60497.png"
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

    @commands.group(
        aliases=["g", "G"],
        brief="Executes a Google command",
        description="Executes a Google command",
    )
    async def google(self: Self, ctx: commands.Context) -> None:
        """The bare .g/G command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @commands.guild_only()
    @google.command(
        aliases=["s", "S"],
        brief="Searches Google",
        description="Returns the top Google search result",
        usage="[query]",
    )
    async def search(self: Self, ctx: commands.Context, *, query: str) -> None:
        """The entry point for the URL search command

        Args:
            ctx (commands.Context): The context in which the command was run in
            query (str): The user inputted string to query google for
        """
        data = {
            "cx": self.bot.file_config.api.api_keys.google_cse,
            "q": query,
            "key": self.bot.file_config.api.api_keys.google,
        }

        items = await self.get_items(self.GOOGLE_URL, data)

        if not items:
            await auxiliary.send_deny_embed(
                message=f"No search results found for: *{query}*", channel=ctx.channel
            )
            return

        config = self.bot.guild_configs[str(ctx.guild.id)]

        embed = None
        embeds = []
        if not getattr(ctx, "image_search", None):
            field_counter = 1
            for index, item in enumerate(items):
                link = item.get("link")
                snippet = item.get("snippet", "<Details Unknown>").replace("\n", "")
                embed = (
                    auxiliary.generate_basic_embed(
                        title=f"Results for {query}", url=self.ICON_URL
                    )
                    if field_counter == 1
                    else embed
                )

                embed.add_field(name=link, value=snippet, inline=False)
                if (
                    field_counter == config.extensions.google.max_responses.value
                    or index == len(items) - 1
                ):
                    embeds.append(embed)
                    field_counter = 1
                else:
                    field_counter += 1

        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)

    @auxiliary.with_typing
    @commands.guild_only()
    @google.command(
        aliases=["i", "is", "I", "IS"],
        brief="Searches Google Images",
        description="Returns the top Google Images search result",
        usage="[query]",
    )
    async def images(self: Self, ctx: commands.Context, *, query: str) -> None:
        """The entry point for the image search command

        Args:
            ctx (commands.Context): The context in which the command was run in
            query (str): The user inputted string to query google for
        """
        data = {
            "cx": self.bot.file_config.api.api_keys.google_cse,
            "q": query,
            "key": self.bot.file_config.api.api_keys.google,
            "searchType": "image",
        }
        items = await self.get_items(self.GOOGLE_URL, data)

        if not items:
            await auxiliary.send_deny_embed(
                message=f"No image search results found for: *{query}*",
                channel=ctx.channel,
            )
            return

        embeds = []
        for item in items:
            link = item.get("link")
            if not link:
                await auxiliary.send_deny_embed(
                    message=(
                        "I had an issue processing Google's response... try again"
                        " later!"
                    ),
                    channel=ctx.channel,
                )
                return
            embeds.append(link)

        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.command(
        aliases=["yt", "YT"],
        brief="Searches YouTube",
        description="Returns the top YouTube search result",
        usage="[query]",
    )
    async def youtube(self: Self, ctx: commands.Context, *, query: str) -> None:
        """The entry point for the youtube search command

        Args:
            ctx (commands.Context): The context in which the command was run in
            query (str): The user inputted string to query google for
        """
        items = await self.get_items(
            self.YOUTUBE_URL,
            data={
                "q": query,
                "key": self.bot.file_config.api.api_keys.google,
                "type": "video",
            },
        )

        if not items:
            await auxiliary.send_deny_embed(
                message=f"No video results found for: *{query}*", channel=ctx.channel
            )
            return

        video_id = items[0].get("id", {}).get("videoId")
        link = f"http://youtu.be/{video_id}"

        links = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            link = f"http://youtu.be/{video_id}" if video_id else None
            if link:
                links.append(link)

        await ui.PaginateView().send(ctx.channel, ctx.author, links)
