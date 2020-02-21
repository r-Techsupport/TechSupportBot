"""Basement _bot main thread.
"""

import asyncio
import importlib
import time

import bot
import utils.helpers
import utils.logger

PREFIX = utils.helpers.get_env_value("COMMAND_PREFIX", ".")
GAME = utils.helpers.get_env_value("GAME", raise_exception=False)
TOKEN = utils.helpers.get_env_value("AUTH_TOKEN")

try:
    HOT_RELOAD = int(utils.helpers.get_env_value("HOT_RELOAD"))
except (ValueError, NameError):
    HOT_RELOAD = 0

if HOT_RELOAD:
    try:
        from restart import RestartManager

        restart_manager = RestartManager(watch_dir="/app/basement_bot")
        restart_manager.start()
    except ImportError:
        restart_manager = None
else:
    restart_manager = None

while True:
    try:
        importlib.reload(bot)
        importlib.reload(utils.helpers)
        importlib.reload(utils.logger)

        log = utils.logger.get_logger("Main Thread")

        log.info("Creating bot instance")
        _bot = bot.BasementBot(prefix=PREFIX, game=GAME)
        if restart_manager:
            restart_manager.set_bot(_bot)

        loop = asyncio.get_event_loop()
        log.info("Starting bot instance")
        loop.run_until_complete(_bot.start(TOKEN))

    except KeyboardInterrupt:
        log.info("Keyboard interrupt detected - attempting graceful shutdown")
        loop.run_until_complete(_bot.shutdown())
        loop.close()
        break

    except Exception as e:
        log.exception(e)

    time.sleep(1)

if restart_manager:
    restart_manager.stop()
