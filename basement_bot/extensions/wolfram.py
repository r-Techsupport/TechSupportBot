import base
import util
from discord.ext import commands


def setup(bot):
    bot.add_cog(Wolfram(bot=bot))


class Wolfram(base.BaseCog):

    API_URL = "http://api.wolframalpha.com/v1/result?appid={}&i={}"
    WOLFRAM_ALPHA_LABEL = "`Wolfram|Alpha`"

    @util.with_typing
    @commands.command(
        name="wa",
        aliases=["math", "wolframalpha"],
        brief="Searches Wolfram Alpha",
        description="Searches the simple answer Wolfram Alpha API",
        usage="[query]",
    )
    async def simple_search(self, ctx, *, query: str):
        query = query.replace(" ", "+")

        url = self.API_URL.format(self.bot.file_config.main.api_keys.wolfram, query)

        response = await self.bot.http_call("get", url, get_raw_response=True)
        if response.status == 501:
            await ctx.send_deny_embed(
                f"{self.WOLFRAM_ALPHA_LABEL} did not like that question"
            )
            return
        if response.status != 200:
            await ctx.send_deny_embed(f"{self.WOLFRAM_ALPHA_LABEL} ran into an error")
            return

        answer = await response.text()
        await ctx.send_confirm_embed(answer)
