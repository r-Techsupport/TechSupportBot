"""Module for logging bot events."""

from __future__ import annotations

import logging
import os
import traceback
from typing import TYPE_CHECKING, Self

import botlogging.embed as embed_lib
import discord

from .common import LogContext, LogLevel

if TYPE_CHECKING:
    import bot


class BotLogger:
    """Logging interface for Discord bots.

    Args:
        discord_bot (bot.TechSupportBot): the bot object
        name (str): the name of the logging channel
        send (bool): Whether or not to allow sending of logs to discord
    """

    class GenericLogLevel:
        """This is the generic log level class
        All other log levels inherit from this

        You should never use this manually
        """

        def __init__(self: Self) -> None:
            self.type = None
            self.console = None
            self.embed = None

    class DebugLogLevel(GenericLogLevel):
        """This is class defining special parameters for debug logs
        This should never be used manually. Use the LogLevel Enum instead

        Args:
            main_console (logging.Logger): The console object to print logs to
        """

        def __init__(self: Self, main_console: logging.Logger) -> None:
            self.type = LogLevel.DEBUG
            self.console = main_console.debug
            self.embed = embed_lib.DebugEmbed

    class InfoLogLevel(GenericLogLevel):
        """This is class defining special parameters for info logs
        This should never be used manually. Use the LogLevel Enum instead

        Args:
            main_console (logging.Logger): The console object to print logs to
        """

        def __init__(self: Self, main_console: logging.Logger) -> None:
            self.type = LogLevel.INFO
            self.console = main_console.info
            self.embed = embed_lib.InfoEmbed

    class WarningLogLevel(GenericLogLevel):
        """This is class defining special parameters for warning logs
        This should never be used manually. Use the LogLevel Enum instead

        Args:
            main_console (logging.Logger): The console object to print logs to
        """

        def __init__(self: Self, main_console: logging.Logger) -> None:
            self.type = LogLevel.WARNING
            self.console = main_console.warning
            self.embed = embed_lib.WarningEmbed

    class ErrorLogLevel(GenericLogLevel):
        """This is class defining special parameters for error logs
        This should never be used manually. Use the LogLevel Enum instead

        Args:
            main_console (logging.Logger): The console object to print logs to
        """

        def __init__(self: Self, main_console: logging.Logger) -> None:
            self.type = LogLevel.ERROR
            self.console = main_console.error
            self.embed = embed_lib.ErrorEmbed

    def __init__(
        self: Self, discord_bot: bot.TechSupportBot, name: str, send: bool
    ) -> None:
        self.bot = discord_bot
        self.console = logging.getLogger(name if name else "root")
        self.send = send
        self.LogLevels = {
            "debug": self.DebugLogLevel(self.console),
            "info": self.InfoLogLevel(self.console),
            "warning": self.WarningLogLevel(self.console),
            "error": self.ErrorLogLevel(self.console),
        }

    async def check_if_should_log(
        self: Self, level: GenericLogLevel, context: LogContext
    ) -> bool:
        """A way to check if the log should be logged
        This takes into account:
            If the env is set to DEBUG
            The level logged at
            The guild logging disable config
            The guild private channels config

        Args:
            level (GenericLogLevel): The Level class that the log is being logged at
            context (LogContext): The context that the log was made in. This can be empty

        Returns:
            bool: True if the log should be logged, False if the log should be ignored
        """
        # Log everything if debug mode is on
        # Otherwise, don't send debug events
        if bool(int(os.environ.get("DEBUG", 0))):
            return True

        # If debug is off, and the log is a debug log, ignore it
        if level.type == LogLevel.DEBUG:
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
        config = self.bot.guild_configs[str(context.guild.id)]

        # Checking to see if guild logging is enabled
        if not config.enable_logging:
            return False

        # Checking to see if log occured in private channels
        if context.channel and str(context.channel.id) in config.private_channels:
            return False

        return True

    async def get_discord_target(
        self: Self, channel_id: str
    ) -> discord.abc.Messageable:
        """This gets the appropriate place to send discord logs to
        This will either be:
            The passed log channel
            The global_alerts_channel
            The bot owners DMs

        Args:
            channel_id (str): The ID of the channel that the log should go to

        Returns:
            discord.abc.Messageable: The channel object to log to
        """
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
        self: Self,
        message: str,
        level: LogLevel,
        context: LogContext = None,
        channel: str = None,
        console_only: bool = False,
        embed: discord.Embed = None,
        exception: Exception = None,
    ) -> None:
        """A comprehensive logging system
        This will log a message, embed, and/or exception to the console and discord

        Args:
            message (str): The simple string representation of the message
            level (LogLevel): The enum of the level the log should be logged at
            context (LogContext, optional): The context the log was made in. Defaults to None.
            channel (str, optional): The string ID of the channel to log to. Defaults to None.
            console_only (bool, optional): If this log should only be sent to the console.
                Defaults to False.
            embed (discord.Embed, optional): If this log is going to be sent to discord,
                you can provide a pre-filled embed.
                The title, description, and color will be overwrote. Defaults to None.
            exception (Exception, optional): The exception item if you wish to
                log an exception with this log.
                Exceptions will be logged in plain text. Defaults to None.
        """
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
        if console_only or not self.send:
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

    def convert_level(self: Self, level: LogLevel) -> GenericLogLevel:
        """A simple function that looks up the LogLevel class from the enum

        Args:
            level (LogLevel): The enum of the log level passed by the logging call

        Returns:
            GenericLogLevel: The specific log class for the log level. Will always be
            an inherited class from Generic, never a true Generic
        """
        return self.LogLevels[level.value]
