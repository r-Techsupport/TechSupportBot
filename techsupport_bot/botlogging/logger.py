"""Module for logging bot events.
"""

from __future__ import annotations

import datetime
import logging
import os
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import bot
import botlogging.embed as embed_lib
import discord


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class LogContext:
    guild: Optional[discord.Guild] = None
    channel: Optional[discord.abc.Messageable] = None


class BotLogger:
    """Logging interface for Discord bots.

    parameters:
        bot (bot.TechSupportBot): the bot object
        name (str): the name of the logging channel
        send (bool): Whether or not to allow sending of logs to discord
    """

    class GenericLogLevel:
        def __init__(self):
            self.type = None
            self.console = None
            self.embed = None

    class DebugLogLevel(GenericLogLevel):
        def __init__(self, main_console):
            self.type = LogLevel.DEBUG
            self.console = main_console.debug
            self.embed = embed_lib.DebugEmbed

    class InfoLogLevel(GenericLogLevel):
        def __init__(self, main_console):
            self.type = LogLevel.INFO
            self.console = main_console.info
            self.embed = embed_lib.InfoEmbed

    class WarningLogLevel(GenericLogLevel):
        def __init__(self, main_console):
            self.type = LogLevel.WARNING
            self.console = main_console.warning
            self.embed = embed_lib.WarningEmbed

    class ErrorLogLevel(GenericLogLevel):
        def __init__(self, main_console):
            self.type = LogLevel.ERROR
            self.console = main_console.error
            self.embed = embed_lib.ErrorEmbed

    def __init__(self, bot: bot.TechSupportBot, name: str, send: bool):
        self.bot = bot
        self.console = logging.getLogger(name if name else "root")
        self.send = send
        self.LogLevels = {
            "debug": self.DebugLogLevel(self.console),
            "info": self.InfoLogLevel(self.console),
            "warning": self.WarningLogLevel(self.console),
            "error": self.ErrorLogLevel(self.console),
        }

    async def check_if_should_log(
        self, level: GenericLogLevel, context: LogContext
    ) -> bool:
        # Log everything if debug mode is on
        # Otherwise, don't send debug events
        if bool(int(os.environ.get("DEBUG", 0))):
            return True
        elif level.type == LogLevel.DEBUG:
            return False

        # Error events should always be sent, ignoring private channels and disabled logging
        if level.type == LogLevel.ERROR:
            return True

        # If no context is passed, we should log only based on level
        if not context:
            return True

        # If there is no guild, the log should always be logged
        if not context.guild:
            return True

        # Get the guilds config
        config = await self.bot.get_context_config(guild=context.guild)

        # Checking to see if guild logging is enabled
        if not config.enable_logging:
            return False

        # Checking to see if log occured in private channels
        if context.channel and str(context.channel.id) in config.private_channels:
            return False

        return True

    async def get_discord_target(self, channel_id: str) -> discord.abc.Messageable:
        # If a channel was passed, that is where the log should be sent
        if channel_id:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                return channel

        # If no channel is passed, determine if there is a global location for logs
        global_channel = (
            self.bot.get_channel(
                int(self.bot.file_config.bot_config.global_alerts_channel)
            )
            if self.bot.file_config.bot_config.global_alerts_channel
            else None
        )

        if global_channel:
            return global_channel

        # If no channel or global channel is set, DM the bot owner
        return await self.bot.get_owner()

    async def send_log(
        self,
        message: str,
        level: LogLevel,
        context: LogContext = None,
        channel: str = None,
        console_only: bool = False,
        embed: discord.Embed = None,
        exception: Exception = None,
    ) -> None:
        log_level = self.convert_level(level)

        # Determine if we should even try sending the log at all
        if not await self.check_if_should_log(log_level, context):
            return

        # Always send message to console, if it should be logged
        log_level.console(message)
        if exception:
            log_level.console(
                "".join(
                    traceback.format_exception(
                        type(exception), exception, exception.__traceback__
                    )
                )
            )

        # If we don't send to discord, we are done
        if console_only:
            return

        # Ensure message is never too long
        if len(message) > 4000:
            message = f"{message[:4000]}..."

        # Get the appropriate target to send to on discord
        log_channel = await self.get_discord_target(channel)

        if embed:
            embed = log_level.embed(message).modify_embed(embed)
        else:
            embed = log_level.embed(message)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            self.console.warning("Failed to send log")

        if exception:
            exception_string = "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )
            exception_string = exception_string.replace("```", "{CODE_BLOCK}")
            send_errors = [
                exception_string[i : i + 1990]
                for i in range(0, len(exception_string), 1990)
            ]
            try:
                for partial_exception in send_errors:
                    await log_channel.send(f"```py\n{partial_exception}```")
            except discord.Forbidden:
                self.console.warning("Failed to send log")

    def convert_level(self, level: LogLevel) -> GenericLogLevel:
        return self.LogLevels[level.value]
