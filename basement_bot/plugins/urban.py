import cogs
import decorate
from discord.ext import commands


def setup(bot):
    bot.add_cog(UrbanDictionary(bot))


class UrbanDictionary(cogs.BasicPlugin):

    BASE_URL = "http://api.urbandictionary.com/v0/define?term="
    SEE_MORE_URL = "https://www.urbandictionary.com/define.php?term="
    HAS_CONFIG = False
    ICON_URL = "https://cdn.icon-icons.com/icons2/114/PNG/512/dictionary_19159.png"

    async def preconfig(self):
        self.cached = {"last_query": None, "last_url": None, "all_urls": []}

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="urb",
        aliases=["urbandictionary", "urban"],
        brief="Searches Urban Dictionary",
        description=("Returns the top Urban Dictionary search result"),
        usage="[query]",
    )
    async def urban(self, ctx, *, query: str):
        response = await self.http_call("get", f"{self.BASE_URL}{query}")
        definitions = response.get("list")

        if not definitions:
            await self.tagged_response(ctx, f"No results found for: *{query}*")
            return

        query_no_spaces = query.replace(" ", "%20")
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
                self.bot.embed_api.Embed(
                    title=f"Results for {query}",
                    description=f"{self.SEE_MORE_URL}{query_no_spaces}",
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

        self.task_paginate(ctx, embeds=embeds, restrict=True)
