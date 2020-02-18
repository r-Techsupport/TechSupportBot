"""Basement _bot main thread.
"""

import asyncio
import importlib

import bot
import utils.helpers

while True:

    _bot = bot.BasementBot(
        prefix=utils.helpers.get_env_value("COMMAND_PREFIX", "."),
        game=utils.helpers.get_env_value("GAME", raise_exception=False),
    )
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(_bot.start(utils.helpers.get_env_value("AUTH_TOKEN")))

    except KeyboardInterrupt:
        loop.run_until_complete(_bot.shutdown())
        loop.close()
        break

    importlib.reload(bot)
    importlib.reload(utils.helpers)
