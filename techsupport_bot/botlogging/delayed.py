"""Module for delayed logging."""

import asyncio
import os
from typing import Any

from botlogging import logger


class DelayedLogger(logger.BotLogger):
    """Logging interface that queues log events to be sent over time.

    parameters:
        bot (bot.TechSupportBot): the bot object
        name (str): the name of the logging channel
        send (bool): Whether or not to allow sending of logs to discord
        wait_time (float): the time to wait between log sends
        queue_size (int): the max number of queue events
    """

    def __init__(self, *args: tuple, **kwargs: dict[str, Any]) -> None:
        self.wait_time = kwargs.pop("wait_time", 1)
        self.queue_size = kwargs.pop("queue_size", 1000)
        self.__send_queue = None
        super().__init__(*args, **kwargs)

    async def send_log(self, *args: tuple, **kwargs: dict[str, Any]) -> None:
        """Adds a log to the queue
        Does nothing different than the Logger send_log function()
        Will disregard debug logs if debug is off
        """

        if kwargs.get("level", None) == logger.LogLevel.DEBUG and not bool(
            int(os.environ.get("DEBUG", 0))
        ):
            return

        await self.__send_queue.put(super().send_log(*args, **kwargs))

    def register_queue(self) -> None:
        """Registers the asyncio.Queue object to make delayed logging possible"""
        self.__send_queue = asyncio.Queue(maxsize=self.queue_size)

    async def run(self) -> None:
        """A forever loop that pulls from the queue and then waits based on the config"""
        while True:
            try:
                coro = await self.__send_queue.get()
                if coro:
                    await coro
                await asyncio.sleep(self.wait_time)
            except Exception:
                pass
