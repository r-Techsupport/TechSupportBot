import asyncio
from random import randint

import http3

from utils.cogs import LoopPlugin
from utils.helpers import get_env_value


def setup(bot):
    bot.add_cog(KanyeQuotes(bot))


class KanyeQuotes(LoopPlugin):

    CHANNEL_ID = get_env_value("KANYE_CHANNEL")
    API_URL = "https://api.kanye.rest"
    MIN_WAIT = int(float(get_env_value("KANYE_MIN_HOURS")) * 3600)
    MAX_WAIT = int(float(get_env_value("KANYE_MAX_HOURS")) * 3600)
    ON_START = bool(int(get_env_value("KANYE_ON_START", "1")))

    async def preconfig(self):
        if self.MIN_WAIT < 0 or self.MAX_WAIT < 0:
            raise RuntimeError("Min and max times must both be greater than 0")
        if self.MAX_WAIT - self.MIN_WAIT <= 0:
            raise RuntimeError(f"Max time must be greater than min time")

        await self.bot.wait_until_ready()
        self.http_client = http3.AsyncClient()

        self.channel = self.bot.get_channel(int(self.CHANNEL_ID))
        if not self.channel:
            raise RuntimeError("Unable to get channel for Kanye Quotes plugin")

        if not self.ON_START:
            self.wait()

    async def execute(self):
        fact = await self.http_client.get(self.API_URL)
        fact = fact.json().get("quote")

        if fact:
            message = f"'*{fact}*' - Kanye West"
            await self.channel.send(message)

    async def wait(self):
        await asyncio.sleep(randint(self.MIN_WAIT, self.MAX_WAIT))
