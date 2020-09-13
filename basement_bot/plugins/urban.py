import json

from discord.ext import commands

from cogs import HttpPlugin
from utils.helpers import priv_response, tagged_response


def setup(bot):
    bot.add_cog(UrbanDictionary(bot))


class UrbanDictionary(HttpPlugin):

    BASE_URL = "http://api.urbandictionary.com/v0/define?term="
    SEE_MORE_URL = "https://www.urbandictionary.com/define.php?term="

    async def preconfig(self):
        self.cached = {"last_query": None, "last_url": None, "all_urls": []}

    @commands.command(
        name="urb",
        brief="Returns the top Urban Dictionary result of search terms",
        description=(
            "Returns the top Urban Dictionary result of the given search terms."
            " Returns nothing if one is not found."
        ),
        usage="[search-terms]",
        help="\nLimitations: Mentions should not be used.",
    )
    async def urban(self, ctx, *args):
        if not args:
            await priv_response(ctx, "I can't search for nothing!")
            return

        args = " ".join(args).lower().strip()
        definitions = await self.http_call("get", f"{self.BASE_URL}{args}")
        definitions = definitions.json().get("list")

        if not definitions:
            await priv_response(ctx, f"No results found for: *{args}*")
            return

        message = (
            definitions[0]
            .get("definition")
            .replace("[", "")
            .replace("]", "")
            .replace("\n", "")
        )
        await tagged_response(
            ctx,
            f'*{message}* ... (See more results: {self.SEE_MORE_URL}{args.replace(" ","%20")})',
        )
