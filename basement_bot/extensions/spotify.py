import aiohttp
import base
import util
from discord.ext import commands


def setup(bot):
    bot.add_cog(Spotify(bot=bot))


class Spotify(base.BaseCog):

    AUTH_URL = "https://accounts.spotify.com/api/token"
    API_URL = "https://api.spotify.com/v1/search"

    async def get_oauth_token(self):
        data = {"grant_type": "client_credentials"}
        response = await self.bot.http_call(
            "post",
            self.AUTH_URL,
            data=data,
            auth=aiohttp.BasicAuth(
                self.bot.file_config.main.api_keys.spotify_client,
                self.bot.file_config.main.api_keys.spotify_key,
            ),
        )

        return response.get("access_token")

    @util.with_typing
    @commands.command(
        brief="Searches Spotify",
        description="Returns Spotify track results",
        usage="[query]",
    )
    async def spotify(self, ctx, *, query: str):
        oauth_token = await self.get_oauth_token()
        if not oauth_token:
            await ctx.send_deny_embed("I couldn't authenticate with Spotify")
            return

        headers = {"Authorization": f"Bearer {oauth_token}"}
        params = {"q": query, "type": "track", "market": "US", "limit": 3}
        response = await self.bot.http_call(
            "get", self.API_URL, headers=headers, params=params
        )

        items = response.get("tracks", {}).get("items", [])

        if not items:
            await ctx.send_deny_embed("I couldn't find any results")
            return

        links = []
        for item in items:
            song_url = item.get("external_urls", {}).get("spotify")
            if not song_url:
                continue
            links.append(song_url)

        if not links:
            await ctx.send_deny_embed("I had trouble parsing the search results")
            return

        ctx.task_paginate(pages=links)
