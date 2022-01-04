import base
import discord
import util
from discord.ext import commands


def setup(bot):
    config = bot.ExtensionConfig()
    config.add(
        key="max_responses",
        datatype="int",
        title="Max Responses",
        description="The max amount of responses per embed page",
        default=1,
    )

    bot.add_cog(UrbanDictionary(bot=bot))
    bot.add_extension_config("urban", config)


class UrbanDictionary(base.BaseCog):

    BASE_URL = "http://api.urbandictionary.com/v0/define?term="
    SEE_MORE_URL = "https://www.urbandictionary.com/define.php?term="
    ICON_URL = "https://cdn.icon-icons.com/icons2/114/PNG/512/dictionary_19159.png"

    @util.with_typing
    @commands.command(
        name="urb",
        aliases=["urbandictionary", "urban"],
        brief="Searches Urban Dictionary",
        description=("Returns the top Urban Dictionary search result"),
        usage="[query]",
    )
    async def urban(self, ctx, *, query: str):
        response = await self.bot.http_call("get", f"{self.BASE_URL}{query}")
        definitions = response.get("list")

        config = await self.bot.get_context_config(ctx)

        if not definitions:
            await util.send_deny_embed(ctx, f"No results found for: *{query}*")
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
                discord.Embed(
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
                field_counter == config.extensions.urban.max_responses.value
                or index == len(definitions) - 1
            ):
                embed.set_thumbnail(url=self.ICON_URL)
                embed.color = discord.Color.dark_green()
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        self.bot.task_paginate(ctx, embeds=embeds, restrict=True)
