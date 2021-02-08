import cogs
import decorate
from discord.ext import commands


def setup(bot):
    bot.add_cog(Wolfram(bot))


class Wolfram(cogs.BasicPlugin):

    API_URL = "http://api.wolframalpha.com/v1/result?appid={}&i={}"

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="wa",
        aliases=["math", "wolframalpha"],
        brief="Searches Wolfram Alpha",
        description="Searches the simple answer Wolfram Alpha API",
        usage="[query]",
    )
    async def simple_search(self, ctx, *, query: str):
        query = query.replace(" ", "+")

        url = self.API_URL.format(self.config.api_key, query)

        response = await self.http_call("get", url, get_raw_response=True)
        answer = await response.text()

        await self.tagged_response(ctx, answer)
