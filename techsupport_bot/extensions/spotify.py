"""Module for the Spotify extension of the discord bot."""
import aiohttp
import base
import ui
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Adding the Spotify configuration to the config file."""
    await bot.add_cog(Spotify(bot=bot))


class Spotify(base.BaseCog):
    """Class for setting up the Spotify extension."""

    AUTH_URL = "https://accounts.spotify.com/api/token"
    API_URL = "https://api.spotify.com/v1/search"

    async def get_oauth_token(self):
        """Method to get an oauth token for the Spotify API."""
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
    @commands.cooldown(3, 60, commands.BucketType.channel)
    @commands.command(
        brief="Searches Spotify",
        description="Returns Spotify track results",
        usage="[query]",
    )
    async def spotify(self, ctx, *, query: str):
        """Method to return a song from the Spotify API."""
        oauth_token = await self.get_oauth_token()
        if not oauth_token:
            await auxiliary.send_deny_embed(
                message="I couldn't authenticate with Spotify", channel=ctx.channel
            )
            return

        headers = {"Authorization": f"Bearer {oauth_token}"}
        params = {"q": query, "type": "track", "market": "US", "limit": 3}
        response = await self.bot.http_call(
            "get", self.API_URL, headers=headers, params=params
        )

        items = response.get("tracks", {}).get("items", [])

        if not items:
            await auxiliary.send_deny_embed(
                message="I couldn't find any results", channel=ctx.channel
            )
            return

        links = []
        for item in items:
            song_url = item.get("external_urls", {}).get("spotify")
            if not song_url:
                continue
            links.append(song_url)

        if not links:
            await auxiliary.send_deny_embed(
                message="I had trouble parsing the search results", channel=ctx.channel
            )
            return

        await ui.PaginateView().send(ctx.channel, ctx.author, links)
