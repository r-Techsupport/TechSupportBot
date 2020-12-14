import json

from cogs import HttpPlugin
from discord.ext import commands
from utils.embed import SafeEmbed
from utils.helpers import paginate, priv_response, tagged_response


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
        embeds = []
        field_counter = 1
        for index, definition in enumerate(definitions):
            message = (
                definition.get("definition")
                .replace("[", "")
                .replace("]", "")
                .replace("\n", "")
            )
            embed = (
                SafeEmbed(
                    title=f"Results for {args}",
                    description=f"{self.SEE_MORE_URL}{args_no_spaces}",
                )
                if field_counter == 1
                else embed
            )
            embed.add_field(
                name=f"{message[:200]}",
                value=definition.get("author", "Author Unknown"),
                inline=False,
            )
            if (
                field_counter == self.config.responses_max
                or index == len(definitions) - 1
            ):
                embed.set_thumbnail(url=self.ICON_URL)
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        await paginate(ctx, embeds=embeds, restrict=True)
