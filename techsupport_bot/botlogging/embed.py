"""Module for log embeds.
"""
import discord


class LogEmbed(discord.Embed):
    """Base log event embed."""

    title = None
    color = None

    def __init__(self, message):
        super().__init__(
            title=self.title.upper(), description=message, color=self.color
        )


class InfoEmbed(LogEmbed):
    """Embed for info level log events."""

    title = "info"
    color = discord.Color.green()


class DebugEmbed(LogEmbed):
    """Embed for debug level log events."""

    title = "debug"
    color = discord.Color.dark_green()


class WarningEmbed(LogEmbed):
    """Embed for warning level log events."""

    title = "warning"
    color = discord.Color.gold()


class ErrorEmbed(LogEmbed):
    """Embed for error level log events."""

    title = "error"
    color = discord.Color.red()


def from_level_name(message, level):
    """Wrapper for generating a log embed.

    parameters:
        message (str): the message
        level (str): the logging level
    """
    level = level.lower()
    if level == "info":
        embed_cls = InfoEmbed
    elif level == "debug":
        embed_cls = DebugEmbed
    elif level == "warning":
        embed_cls = WarningEmbed
    elif level == "error":
        embed_cls = ErrorEmbed
    else:
        raise ValueError("invalid log level provided")

    embed = embed_cls(message)

    return embed
