import cogs
import decorate
from discord.ext import commands


def setup(bot):
    bot.add_cog(Googler(bot))


class Googler(cogs.HttpPlugin):

    PLUGIN_NAME = __name__
    GOOGLE_URL = "https://www.googleapis.com/customsearch/v1"
    YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/search?part=id&maxResults=1"

    async def get_items(self, url, data):
        response = await self.http_call("get", url, params=data)
        return response.get("items")

    @commands.group(
        aliases=["g"],
        brief="Executes a Google command",
        description="Executes a Google command",
    )
    async def google(self, ctx):
        pass

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @google.command(
        aliases=["s"],
        brief="Searches Google",
        description="Returns the top Google search result",
        usage="[query]",
    )
    async def search(self, ctx, *, query: str):
        data = {
            "cx": self.config.cse_id,
            "q": query,
            "key": self.config.dev_key,
        }

        items = await self.get_items(self.GOOGLE_URL, data)

        if not items:
            await self.bot.h.tagged_response(
                ctx, f"No search results found for: *{query}*"
            )
            return

        embed = None
        embeds = []
        if not getattr(ctx, "image_search", None):
            field_counter = 1
            for index, item in enumerate(items):
                link = item.get("link")
                snippet = item.get("snippet", "<Details Unknown>").replace("\n", "")
                embed = (
                    self.bot.embed_api.Embed(
                        title=f"Results for {query}", value="https://google.com"
                    )
                    if field_counter == 1
                    else embed
                )
                embed.add_field(name=link, value=snippet, inline=False)
                if (
                    field_counter == self.config.responses_max
                    or index == len(items) - 1
                ):
                    embed.set_thumbnail(
                        url="https://cdn.icon-icons.com/icons2/673/PNG/512/Google_icon-icons.com_60497.png"
                    )
                    embeds.append(embed)
                    field_counter = 1
                else:
                    field_counter += 1

        self.bot.h.task_paginate(ctx, embeds=embeds, restrict=True)

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @google.command(
        aliases=["i", "is"],
        brief="Searches Google Images",
        description="Returns the top Google Images search result",
        usage="[query]",
    )
    async def images(self, ctx, query: str):
        data = {
            "cx": self.config.cse_id,
            "q": query,
            "key": self.config.dev_key,
            "searchType": "image",
        }
        items = await self.get_items(self.GOOGLE_URL, data)

        if not items:
            await self.bot.h.tagged_response(
                ctx, f"No image search results found for: *{query}*"
            )
            return

        embeds = []
        for item in items:
            link = item.get("link")
            if not link:
                await self.bot.h.tagged_response(
                    ctx,
                    "I had an issue processing Google's response... try again later!",
                )
                return
            embeds.append(link)

        self.bot.h.task_paginate(ctx, embeds=embeds, restrict=True)

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        aliases=["yt"],
        brief="Searches YouTube",
        description=("Returns the top YouTube search result"),
        usage="[query]",
    )
    async def youtube(self, ctx, *, query: str):
        items = await self.get_items(
            self.YOUTUBE_URL,
            data={
                "q": query,
                "key": self.config.dev_key,
                "type": "video",
            },
        )

        if not items:
            await self.bot.h.tagged_response(
                ctx, f"No video results found for: *{query}*"
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

        self.bot.h.task_paginate(ctx, links, restrict=True)
