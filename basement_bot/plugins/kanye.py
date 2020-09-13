import asyncio
from random import randint

from cogs import HttpPlugin, LoopPlugin
from utils.helpers import get_env_value


def setup(bot):
    bot.add_cog(KanyeQuotes(bot))


class KanyeQuotes(LoopPlugin, HttpPlugin):

    CHANNEL_ID = get_env_value("KANYE_CHANNEL")
    API_URL = "https://api.kanye.rest"
    MIN_WAIT = int(float(get_env_value("KANYE_MIN_HOURS")) * 3600)
    MAX_WAIT = int(float(get_env_value("KANYE_MAX_HOURS")) * 3600)
    ON_START = bool(int(get_env_value("KANYE_ON_START", "1")))

    async def loop_preconfig(self):
        if self.MIN_WAIT < 0 or self.MAX_WAIT < 0:
            raise RuntimeError("Min and max times must both be greater than 0")
        if self.MAX_WAIT - self.MIN_WAIT <= 0:
            raise RuntimeError(f"Max time must be greater than min time")

        self.channel = self.bot.get_channel(int(self.CHANNEL_ID))
        if not self.channel:
            raise RuntimeError("Unable to get channel for Kanye Quotes plugin")

        if not self.ON_START:
            await self.wait()

    async def execute(self):
        response = await self.http_call("get", self.API_URL)
        quote = response.json().get("quote")

        if quote:
            message = f"'*{quote}*' - Kanye West"
            await self.channel.send(message)

    async def wait(self):
        await asyncio.sleep(randint(self.MIN_WAIT, self.MAX_WAIT))
