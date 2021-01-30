import cogs
import decorate
from discord.ext import commands


def setup(bot):
    bot.add_cog(Wolfram(bot))


class Wolfram(cogs.HttpPlugin):

    PLUGIN_NAME = __name__
    API_URL = "http://api.wolframalpha.com/v1/result?appid={}&i={}"

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="wa",
        aliases=["math"],
        brief="Search Wolfram Alpha",
        description="Searches the simple answer Wolfram Alpha API",
        usage="[query]",
    )
    async def simple_search(self, ctx, *, query: str):
        query = query.replace(" ", "+")

        url = self.API_URL.format(self.config.api_key, query)

        response = await self.http_call("get", url, get_raw_response=True)

        await self.bot.h.tagged_response(ctx, response.text)
