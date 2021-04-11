import base
import decorate
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[Wolfram])


class Wolfram(base.BaseCog):

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

        url = self.API_URL.format(self.bot.config.main.api_keys.wolfram, query)

        response = await self.bot.http_call("get", url, get_raw_response=True)
        answer = await response.text()

        await self.bot.send_with_mention(ctx, answer)
