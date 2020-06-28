import random

import http3
from discord.ext import commands

from cogs import BasicPlugin
from utils.helpers import get_env_value, priv_response, tagged_response


def setup(bot):
    bot.add_cog(Giphy(bot))


class Giphy(BasicPlugin):

    DEV_KEY = get_env_value("GIPHY_DEV_KEY", raise_exception=False)
    GIPHY_URL = (
        "http://api.giphy.com/v1/gifs/search?q={}&api_key={}&limit={}"
    )
    SEARCH_LIMIT = 250

    @commands.command(
        name="giphy",
        brief="Grabs a random Giphy image",
        description=("Grabs a random Giphy image based on your search."),
        usage="[search-terms]",
        help="\nLimitations: Mentions should not be used.",
    )
    async def giphy(self, ctx, *args):
        if not self.DEV_KEY:
            await priv_response(ctx, "Sorry, I don't have the Giphy API key!")
            return
        if not args:
            await priv_response(ctx, "I can't search for nothing!")
            return

        http_client = http3.AsyncClient()
        args_q = "+".join(args)
        response = await http_client.get(
            self.GIPHY_URL.format(args_q, self.DEV_KEY, self.SEARCH_LIMIT)
        )
        response = response.json()
        data = response.get("data")

        if not data:
            args = f"*{args}*"
            await priv_response(ctx, f"No search results found for: {args}")
            return

        gif = random.choice(data)

        await tagged_response(ctx, gif.get("images", {}).get("original", {}).get("url"))
