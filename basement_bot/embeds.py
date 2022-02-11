"""Module for builtin embeds.
"""

import discord


class SaneEmbed(discord.Embed):
    """An embed that is guaranteed to sanely handle validation constraints."""

    def add_field(self, *, name, value, inline=True):
        """Wraps the embed method with trimming."""
        name = name[:256]
        value = value[:1024]
        super().add_field(name=name, value=value, inline=inline)

    def set_author(
        self, *, name, url=discord.Embed.Empty, icon_url=discord.Embed.Empty
    ):
        """Wraps the embed method with trimming."""
        name = name[:256]
        super().set_author(name=name, url=url, icon_url=icon_url)

    def insert_field_at(self, index, *, name, value, inline=True):
        """Wraps the embed method with trimming."""
        name = name[:256]
        value = value[:1024]
        super().insert_field_at(index, name=name, value=value, inline=inline)

    def set_field_at(self, index, *, name, value, inline=True):
        """Wraps the embed method with trimming."""
        name = name[:256]
        value = value[:1024]
        super().set_field_at(index, name=name, value=value, inline=inline)

    def set_footer(self, *, text=discord.Embed.Empty, icon_url=discord.Embed.Empty):
        """Wraps the embed method with trimming."""
        if isinstance(text, str):
            text = text[:2048]
        super().set_footer(text=text, icon_url=icon_url)


class ConfirmEmbed(SaneEmbed):
    """An embed for confirmation responses.

    parameters:
        message (str): the response message
    """

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        super().__init__(*args, **kwargs)
        self.title = "👍"
        self.description = message
        self.color = discord.Color.green()


class DenyEmbed(SaneEmbed):
    """An embed for deny responses.

    parameters:
        message (str): the response message
    """

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        super().__init__(*args, **kwargs)
        self.title = "👎"
        self.description = message
        self.color = discord.Color.red()
