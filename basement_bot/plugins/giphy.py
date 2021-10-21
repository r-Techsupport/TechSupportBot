import random

import base
import decorate
import util
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[Giphy])


class Giphy(base.BaseCog):

    GIPHY_URL = "http://api.giphy.com/v1/gifs/search?q={}&api_key={}&limit={}"
    SEARCH_LIMIT = 10

    @staticmethod
    def parse_url(url):
        index = url.find("?cid=")
        return url[:index]

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.command(
        name="giphy",
        brief="Grabs a random Giphy image",
        description="Grabs a random Giphy image based on your search",
        usage="[query]",
    )
    async def giphy(self, ctx, *, query: str):
        response = await util.http_call(
            "get",
            self.GIPHY_URL.format(
                query.replace(" ", "+"),
                self.bot.config.main.api_keys.giphy,
                self.SEARCH_LIMIT,
            ),
        )

        data = response.get("data")
        if not data:
            await util.send_with_mention(ctx, f"No search results found for: *{query}*")
            return

        embeds = []
        for item in data:
            url = item.get("images", {}).get("original", {}).get("url")
            url = self.parse_url(url)
            embeds.append(url)

        self.bot.task_paginate(ctx, embeds, restrict=True)
