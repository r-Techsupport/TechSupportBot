"""Module for logging bot events.
"""

from __future__ import annotations

import datetime
import logging
import os
import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

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

    # this defaults to False because most logs shouldn't send out
    DEFAULT_LOG_SEND = False
    # this defaults to True because most error logs should send out
    DEFAULT_ERROR_LOG_SEND = True

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
        console_only: bool = True,
        embed: discord.Embed = None,
        exception: Exception = None,
    ) -> None:
        log_level = self.convert_level(level)

        # Determine if we should even try sending the log at all
        if context and not await self.check_if_should_log(log_level, context):
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
        if not console_only:
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

    async def info(self, message, **kwargs):
        """Logs at the INFO level.

        parameters:
            message (str): the message to log
            embed (discord.Embed): the embed to send to Discord
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        await self.handle_generic_log(message, self.console.info, **kwargs)

    async def debug(self, message, **kwargs):
        """Logs at the DEBUG level.

        parameters:
            message (str): the message to log
            embed (discord.Embed): the embed to send to Discord
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        await self.handle_generic_log(message, self.console.debug, **kwargs)

    async def warning(self, message, **kwargs):
        """Logs at the WARNING level.

        parameters:
            message (str): the message to log
            embed (discord.Embed): the embed to send to Discord
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        await self.handle_generic_log(message, self.console.warning, **kwargs)

    async def handle_generic_log(self, message, console, **kwargs):
        """Handles most logging contexts.

        parameters:
            message (str): the message to log
            embed (discord.Embed): the embed to send to Discord
            level (str): the logging level
            console (func): logging level method
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
        """
        console_only = self._is_console_only(kwargs, is_error=False)

        channel_id = kwargs.get("channel", None)

        console(message)

        if console_only:
            return

        channel = self.bot.get_channel(int(channel_id)) if channel_id else None
        global_channel = (
            self.bot.get_channel(
                int(self.bot.file_config.bot_config.global_alerts_channel)
            )
            if self.bot.file_config.bot_config.global_alerts_channel
            else None
        )

        if channel:
            target = channel
        elif self.bot.file_config.bot_config.global_alerts_channel:
            target = global_channel
        else:
            target = await self.bot.get_owner()

        if not target:
            self.console.warning(
                "Could not determine Discord target to send %s log", console.__name__
            )
            return

        base_embed = embed_lib.from_level_name(message, console.__name__)

        embed = kwargs.get("embed", base_embed)
        # override embed features with base
        embed.title = base_embed.title
        embed.color = base_embed.color
        embed.description = base_embed.description

        embed.timestamp = kwargs.get("time", datetime.datetime.utcnow())

        try:
            await target.send(embed=embed)
        except discord.Forbidden:
            pass

    async def error(self, message, **kwargs):
        """Logs at the ERROR level.

        parameters:
            message (str): the message to log
            embed (discord.Embed): the embed to send to Discord
            exception (Exception): the exception object
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
            critical (bool): True if the critical error handler should be invoked
        """
        await self.handle_error_log(message, **kwargs)

    async def handle_error_log(self, message, **kwargs):
        """Handles error logging.

        parameters:
            message (str): the message to log with the error
            embed (discord.Embed): the embed to send to Discord
            exception (Exception): the exception object
            send (bool): The reverse of the above (overrides console_only)
            channel (int): the ID of the channel to send the log to
            critical (bool): True if the critical error handler should be invoked
        """
        exception = kwargs.get("exception", None)
        critical = kwargs.get("critical")
        channel_id = kwargs.get("channel", None)
        console_only = self._is_console_only(kwargs, is_error=True)

        self.console.error(message)

        if console_only:
            return

        exception_string = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
        exception_string = exception_string.replace("```", "{CODE_BLOCK}")

        embed = kwargs.get("embed", embed_lib.ErrorEmbed(message))
        embed.timestamp = kwargs.get("time", datetime.datetime.utcnow())

        if channel_id:
            channel = self.bot.get_channel(int(channel_id))
        else:
            channel = None

        # tag user if critical
        if channel:
            content = channel.guild.owner.mention if critical else None
            target = channel
        else:
            target = await self.bot.get_owner()
            content = target.mention if critical else None

        if not target:
            self.console.warning("Could not determine Discord target to send ERROR log")
            return

        send_errors = [
            exception_string[i : i + 1990]
            for i in range(0, len(exception_string), 1990)
        ]
        try:
            await target.send(content=content, embed=embed)
            for partial_exception in send_errors:
                await target.send(f"```py\n{partial_exception}```")
        except discord.Forbidden:
            pass

    def _is_console_only(self, kwargs, is_error):
        """Determines from a kwargs dict if console_only is absolutely True.

        This is so `send` can be provided as a convenience arg.

        parameters:
            kwargs (dict): the kwargs to parse
            is_error (bool): True if the decision is for an error log
        """
        # check if sending is disabled globally
        if not self.send:
            return True
        default_send = (
            self.DEFAULT_ERROR_LOG_SEND if is_error else self.DEFAULT_LOG_SEND
        )
        return not kwargs.get("send", default_send)
