"""Module for log embeds.
"""
import datetime

import discord


class LogEmbed(discord.Embed):
    """Base log event embed."""

    title = None
    color = None

    def __init__(self, message):
        super().__init__(
            title=self.title.upper(), description=message, color=self.color
        )
        self.timestamp = datetime.datetime.utcnow()

    def modify_embed(self, embed):
        embed.title = self.title
        embed.color = self.color
        embed.description = self.description
        embed.timestamp = datetime.datetime.utcnow()

        return embed


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
