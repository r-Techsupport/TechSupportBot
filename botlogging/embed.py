"""Module for log embeds."""

from __future__ import annotations

import datetime
from typing import Self

import discord


class LogEmbed(discord.Embed):
    """Base log event embed.
    Do not create this directly

    Args:
        message (str): The message to log. Will become the description of an embed

    Attributes:
        title (str): The title of the embed
        color (discord.Color): The color of the embed
    """

    title: str = None
    color: discord.Color = None

    def __init__(self: Self, message: str) -> None:
        super().__init__(
            title=self.title.upper(), description=message, color=self.color
        )
        self.timestamp = datetime.datetime.utcnow()

    def modify_embed(self: Self, embed: discord.Embed) -> discord.Embed:
        """This modifies an existing embed to match with the LogEmbed style

        Args:
            embed (discord.Embed): The embed to modify

        Returns:
            discord.Embed: The modified embed
        """
        embed.title = self.title
        embed.color = self.color
        embed.description = self.description
        embed.timestamp = datetime.datetime.utcnow()

        return embed


class InfoEmbed(LogEmbed):
    """Embed for info level log events.

    Attributes:
        title (str): The title of the embed
        color (discord.Color): The color of the embed
    """

    title: str = "info"
    color: discord.Color = discord.Color.green()


class DebugEmbed(LogEmbed):
    """Embed for debug level log events.

    Attributes:
        title (str): The title of the embed
        color (discord.Color): The color of the embed
    """

    title: str = "debug"
    color: discord.Color = discord.Color.dark_green()


class WarningEmbed(LogEmbed):
    """Embed for warning level log events.

    Attributes:
        title (str): The title of the embed
        color (discord.Color): The color of the embed
    """

    title: str = "warning"
    color: discord.Color = discord.Color.gold()


class ErrorEmbed(LogEmbed):
    """Embed for error level log events.

    Attributes:
        title (str): The title of the embed
        color (discord.Color): The color of the embed
    """

    title: str = "error"
    color: discord.Color = discord.Color.red()
