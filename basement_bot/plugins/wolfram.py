from cogs import HttpPlugin
from discord.ext import commands
from utils.helpers import priv_response, tagged_response


def setup(bot):
    bot.add_cog(Wolfram(bot))


class Wolfram(HttpPlugin):

    PLUGIN_NAME = __name__
    API_URL = "http://api.wolframalpha.com/v1/result?appid=%s&i=%s"

    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="wa", 
        aliases=["math"],         
        brief="Search Wolfram Alpha",
        description="Searches the simple answer Wolfram Alpha API",
        usage="[query]"
    )
    async def simple_search(self, ctx, *args):
        if not args:
            await priv_response(ctx, "Please provide a query!")
            return

        query = "+".join(args)

        url = self.API_URL % (self.config.api_key, query)

        response = await self.http_call("get", url)

        if not response.text:
            await priv_response(ctx, "No results found")
            return

        await tagged_response(ctx, response.text)
