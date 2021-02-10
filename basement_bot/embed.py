"""Provides an interface for complex embed generation.
"""
from discord import Embed as DiscordEmbed


class Embed(DiscordEmbed):
    """Custom BasementBot embed."""

    @classmethod
    def from_kwargs(cls, title=None, description=None, **kwargs):
        """Wrapper for generating an embed from a set of key, values.

        parameters:
            title (str): the title for the embed
            description (str): the description for the embed
            **kwargs (dict): a set of keyword values to be displayed
        """
        embed = cls(title=title, description=description)
        for key, value in kwargs.items():
            embed.add_field(name=key, value=value, inline=False)
        return embed

    def add_field(self, *, name, value, inline=True):
        """Wraps the default add_field method with argument length checks.

        parameters:
            name (str): the name of the field
            value (str): the value of the field
            inline (bool): True if the field should be inlined with the last field
        """

        # if the value cannot be stringified, it is not valid
        try:
            value = str(value)
        except Exception:
            value = ""

        if len(name) > 256:
            name = name[:256]
        if len(value) > 256:
            value = value[:256]

        return super().add_field(name=name, value=value, inline=inline)


# pylint: disable=too-few-public-methods
class EmbedAPI:
    """API for generating embeds.

    parameters:
        bot (BasementBot): the bot object
    """

    def __init__(self, bot):
        self.bot = bot

    Embed = Embed
