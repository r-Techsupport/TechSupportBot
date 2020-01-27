import asyncio
from random import randint

import http3

from utils.helpers import get_env_value

CHANNEL_ID = get_env_value("KANYE_FACTS_CHANNEL")
API_URL = "https://api.kanye.rest"
MIN_WAIT = 3600
MAX_WAIT = 21600


def setup(bot):
    bot.loop.create_task(kanye_fact(bot))


async def kanye_fact(bot):
    await bot.wait_until_ready()
    http_client = http3.AsyncClient()

    while True:
        channel = bot.get_channel(int(CHANNEL_ID))
        if not channel:
            break

        fact = await http_client.get(API_URL)
        fact = fact.json().get("quote")

        if fact:
            message = f"'*{fact}*' - Kanye West"
            await channel.send(message)

        await asyncio.sleep(randint(MIN_WAIT, MAX_WAIT))
