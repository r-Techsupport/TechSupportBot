import cogs
import decorate
from discord.ext import commands


def setup(bot):
    bot.add_cog(Spotify(bot))


class Spotify(cogs.BasicPlugin):

    PLUGIN_NAME = __name__

    AUTH_URL = "https://accounts.spotify.com/api/token"
    API_URL = "https://api.spotify.com/v1/search"

    async def get_oauth_token(self):
        data = {"grant_type": "client_credentials"}
        response = await self.http_call(
            "post",
            self.AUTH_URL,
            data=data,
            auth=(self.config.client_id, self.config.client_secret),
        )

        return response.get("access_token")

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Searches Spotify",
        description="Returns Spotify track results",
        usage="[query]",
    )
    async def spotify(self, ctx, *, query: str):
        oauth_token = await self.get_oauth_token()
        if not oauth_token:
            await self.tagged_response(ctx, "I couldn't authenticate with Spotify")
            return

        headers = {"Authorization": f"Bearer {oauth_token}"}
        params = {"q": query, "type": "track", "market": "US", "limit": 3}
        response = await self.http_call(
            "get", self.API_URL, headers=headers, params=params
        )

        items = response.get("tracks", {}).get("items", [])

        if not items:
            await self.tagged_response(ctx, "I couldn't find any results")
            return

        links = []
        for item in items:
            song_url = item.get("external_urls", {}).get("spotify")
            if not song_url:
                continue
            links.append(song_url)

        if not links:
            await self.tagged_response("I had trouble parsing the search results")
            return

        self.task_paginate(ctx, links, restrict=True)
