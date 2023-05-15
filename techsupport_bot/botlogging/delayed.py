"""Module for delayed logging.
"""

import asyncio

from botlogging import logger


class DelayedLogger(logger.BotLogger):
    """Logging interface that queues log events to be sent over time.

    parameters:
        bot (bot.TechSupportBot): the bot object
        name (str): the name of the logging channel
        wait_time (float): the time to wait between log sends
        queue_size (int): the max number of queue events
    """

    def __init__(self, *args, **kwargs):
        self.wait_time = kwargs.pop("wait_time", 1)
        self.queue_size = kwargs.pop("queue_size", 1000)
        self.__send_queue = None
        super().__init__(*args, **kwargs)

    async def info(self, message, *args, **kwargs):
        await self.__send_queue.put(super().info(message, *args, **kwargs))

    async def debug(self, message, *args, **kwargs):
        await self.__send_queue.put(super().debug(message, *args, **kwargs))

    async def warning(self, message, *args, **kwargs):
        await self.__send_queue.put(super().warning(message, *args, **kwargs))

    async def error(self, message, *args, **kwargs):
        await self.__send_queue.put(super().error(message, *args, **kwargs))

    def register_queue(self):
        self.__send_queue = asyncio.Queue(maxsize=self.queue_size)

    async def __run(self):
        while True:
            try:
                coro = await self.__send_queue.get()
                if coro:
                    await coro
                await asyncio.sleep(self.wait_time)
            except:
                pass
