import json

from cogs import HttpPlugin
from discord import Embed
from discord.ext import commands
from utils.helpers import priv_response, tagged_response


def setup(bot):
    bot.add_cog(UrbanDictionary(bot))


class UrbanDictionary(HttpPlugin):

    PLUGIN_NAME = __name__
    BASE_URL = "http://api.urbandictionary.com/v0/define?term="
    SEE_MORE_URL = "https://www.urbandictionary.com/define.php?term="
    HAS_CONFIG = False
    ICON_URL = "https://cdn.icon-icons.com/icons2/114/PNG/512/dictionary_19159.png"

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

        args_no_spaces = args.replace(" ", "%20")
        embed = Embed(
            title=f"Results for {args}",
            description=f"{self.SEE_MORE_URL}{args_no_spaces}",
        )
        embed.set_thumbnail(url=self.ICON_URL)
        for index, definition in enumerate(definitions):
            message = (
                definition.get("definition")
                .replace("[", "")
                .replace("]", "")
                .replace("\n", "")
            )
            embed.add_field(
                name=f"{message[:200]}",
                value=definition.get("author", "Author Unknown"),
                inline=False,
            )
            if index + 1 == self.config.responses_max:
                break

        await tagged_response(ctx, embed=embed)
