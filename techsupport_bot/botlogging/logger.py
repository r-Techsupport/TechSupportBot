"""Module for logging bot events.
"""

import datetime
import logging
import traceback

import botlogging.embed as embed_lib
import discord


class BotLogger:
    """Logging interface for Discord bots.

    parameters:
        bot (bot.TechSupportBot): the bot object
        name (str): the name of the logging channel
    """

    # this defaults to False because most logs shouldn't send out
    DEFAULT_LOG_SEND = False
    # this defaults to True because most error logs should send out
    DEFAULT_ERROR_LOG_SEND = True

    def __init__(self, **kwargs):
        self.bot = kwargs.get("bot")
        self.console = logging.getLogger(kwargs.get("name", "root"))
        self.send = kwargs.get("send")

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

        if channel:
            target = channel
        else:
            target = await self.bot.get_owner()

        if not target:
            # pylint: disable=logging-fstring-interpolation
            self.console.warning(
                f"Could not determine Discord target to send {console.__name__} log"
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
        exception_string = exception_string[:1992]

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

        try:
            await target.send(content=content, embed=embed)
            await target.send(f"```py\n{exception_string}```")
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
