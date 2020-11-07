import random

from cogs import HttpPlugin
from discord.ext import commands
from utils.helpers import priv_response, tagged_response


def setup(bot):
    bot.add_cog(Giphy(bot))


class Giphy(HttpPlugin):

    PLUGIN_NAME = __name__
    GIPHY_URL = "http://api.giphy.com/v1/gifs/search?q={}&api_key={}&limit={}"
    SEARCH_LIMIT = 5

    async def preconfig(self):
        self.cached = {"last_query": None, "last_url": None, "all_urls": []}

    @staticmethod
    def parse_url(url):
        index = url.find("?cid=")
        return url[:index]

    @commands.command(
        name="giphy",
        brief="Grabs a random Giphy image",
        description=("Grabs a random Giphy image based on your search."),
        usage="[search-terms]",
        help="\nLimitations: Mentions should not be used.",
    )
    async def giphy(self, ctx, *args):
        if not args:
            await priv_response(ctx, "I can't search for nothing!")
            return

        args_ = " ".join(args)
        if self.cached.get("last_query") == args:
            url = self.parse_url(random.choice(self.cached.get("all_urls")))
            await tagged_response(ctx, url)
            return

        args_q = "+".join(args)
        response = await self.http_call(
            "get",
            self.GIPHY_URL.format(args_q, self.config.dev_key, self.SEARCH_LIMIT),
        )
        response = response.json()
        data = response.get("data")

        if not data:
            args_f = f"*{args_}*"
            await priv_response(ctx, f"No search results found for: {args_f}")
            return

        while True:
            url = random.choice(data).get("images", {}).get("original", {}).get("url")
            url = self.parse_url(url)
            if url != self.cached.get("last_url"):
                break

        await tagged_response(ctx, url)

        urls_list = []
        for gif_ in data:
            urls_list.append(gif_.get("images", {}).get("original", {}).get("url"))
        self.cached = {"last_query": args_, "last_url": url, "all_urls": urls_list}
