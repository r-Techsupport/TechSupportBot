import asyncio
from random import randint

from discord import Embed

from cogs import HttpPlugin, LoopPlugin


def setup(bot):
    bot.add_cog(KanyeQuotes(bot))


class KanyeQuotes(LoopPlugin, HttpPlugin):

    PLUGIN_NAME = __name__
    API_URL = "https://api.kanye.rest"

    async def loop_preconfig(self):
        min_wait = self.config.min_hours
        max_wait = self.config.max_hours

        if min_wait < 0 or max_wait < 0:
            raise RuntimeError("Min and max times must both be greater than 0")
        if max_wait - min_wait <= 0:
            raise RuntimeError(f"Max time must be greater than min time")

        self.channel = self.bot.get_channel(self.config.channel)
        if not self.channel:
            raise RuntimeError("Unable to get channel for Kanye Quotes plugin")

        if not self.config.on_start:
            await self.wait()

    async def execute(self):
        response = await self.http_call("get", self.API_URL)
        quote = response.json().get("quote")

        if quote:
            message = f"'*{quote}*' - Kanye West"
            embed = Embed(title=quote, description="Kanye Quest")
            embed.set_thumbnail(url="https://i.imgur.com/ITmTXGz.jpg")
            await self.channel.send(embed=embed)

    async def wait(self):
        await asyncio.sleep(
            randint(self.config.min_hours * 3600, self.config.max_hours * 3600,)
        )
