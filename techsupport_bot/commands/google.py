"""Module for the google extension for the discord bot."""

import ui
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands


async def setup(bot):
    """Adding google extension config to the config file."""

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
    """Class for the google extension for the discord bot."""

    GOOGLE_URL = "https://www.googleapis.com/customsearch/v1"
    YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/search?part=id&maxResults=10"
    ICON_URL = (
        "https://cdn.icon-icons.com/icons2/673/PNG/512/Google_icon-icons.com_60497.png"
    )

    async def get_items(self, url, data):
        """Method to get an item from google's api."""
        response = await self.bot.http_functions.http_call(
            "get", url, params=data, use_cache=True
        )
        return response.get("items")

    @commands.group(
        aliases=["g", "G"],
        brief="Executes a Google command",
        description="Executes a Google command",
    )
    async def google(self, ctx):
        """Method to add command to search google."""

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
    async def search(self, ctx, *, query: str):
        """Method for searching results on google."""
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
                if field_counter == 1:
                    embed = auxiliary.generate_basic_embed(
                        title=f"Results for {query}", url=self.ICON_URL
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
    async def images(self, ctx, *, query: str):
        """Method to get an image from a google search."""
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
    async def youtube(self, ctx, *, query: str):
        """Method to get the youtube link form searching google."""
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
