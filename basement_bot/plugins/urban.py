import json

import http3
from discord.ext import commands

from cogs import BasicPlugin
from utils.helpers import priv_response, tagged_response


def setup(bot):
    bot.add_cog(UrbanDictionary(bot))


class UrbanDictionary(BasicPlugin):

    BASE_URL = "http://api.urbandictionary.com/v0/define?term="
    SEE_MORE_URL = "https://www.urbandictionary.com/define.php?term="

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

        http_client = http3.AsyncClient()
        args = " ".join(args).lower().strip()
        definitions = await http_client.get(f"{self.BASE_URL}{args}")
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
