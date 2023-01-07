"""Module for delayed logging.
"""

import asyncio

from botlogging import logger


class DelayedLogger(logger.BotLogger):
    """Logging interface that queues log events to be sent over time.

    parameters:
        bot (bot.BasementBot): the bot object
        name (str): the name of the logging channel
        wait_time (float): the time to wait between log sends
        queue_size (int): the max number of queue events
    """

    def __init__(self, *args, **kwargs):
        self.wait_time = kwargs.pop("wait_time", 1)
        self.__send_queue = asyncio.Queue(maxsize=kwargs.pop("queue_size", 1000))
        super().__init__(*args, **kwargs)

        self.bot.loop.create_task(self.__run())

    async def info(self, message, *args, **kwargs):
        await self.__send_queue.put(super().info(message, *args, **kwargs))

    async def debug(self, message, *args, **kwargs):
        await self.__send_queue.put(super().debug(message, *args, **kwargs))

    async def warning(self, message, *args, **kwargs):
        await self.__send_queue.put(super().warning(message, *args, **kwargs))

    async def error(self, message, *args, **kwargs):
        await self.__send_queue.put(super().error(message, *args, **kwargs))

    async def __run(self):
        while True:
            try:
                coro = await self.__send_queue.get()
                if coro:
                    await coro
                await asyncio.sleep(self.wait_time)
            except:
                pass
