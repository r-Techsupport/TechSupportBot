import asyncio
from random import randint

import http3

from utils.helpers import get_env_value

CHANNEL_ID = get_env_value("KANYE_CHANNEL")
API_URL = "https://api.kanye.rest"
MIN_WAIT = int(get_env_value("KANYE_MIN_HOURS")) * 3600
MAX_WAIT = int(get_env_value("KANYE_MAX_HOURS")) * 3600
ON_START = bool(int(get_env_value("KANYE_ON_START", "1")))


def setup(bot):
    if MIN_WAIT < 0 or MAX_WAIT < 0:
        raise RuntimeError("Min and max times must both be greater than 0")
    if MAX_WAIT - MIN_WAIT <= 0:
        raise RuntimeError(f"Max time must be greater than min time")
    bot.loop.create_task(kanye_fact(bot))


async def kanye_fact(bot):
    await bot.wait_until_ready()
    http_client = http3.AsyncClient()

    channel = bot.get_channel(int(CHANNEL_ID))
    if not channel:
        return

    if not ON_START:
        await asyncio.sleep(randint(MIN_WAIT, MAX_WAIT))

    while True:
        fact = await http_client.get(API_URL)
        fact = fact.json().get("quote")

        if fact:
            message = f"'*{fact}*' - Kanye West"
            await channel.send(message)

        await asyncio.sleep(randint(MIN_WAIT, MAX_WAIT))
