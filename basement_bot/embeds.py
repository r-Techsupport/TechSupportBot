"""Provides an interface for complex embed generation.
"""
from discord import Embed as DiscordEmbed

# this API is still a WIP and will expand as necessary

class Embed(DiscordEmbed):
    """Base Embed object.
    """

    # embeds strings tend to max out at 256 length
    FIELD_VALUE_TRIM = 256
    FIELD_NAME_TRIM = 256

    @classmethod
    def from_kwargs(cls, title=None, description=None, all_inline=False, **kwargs):
        """Wrapper for generating an embed from a set of key, values.

        parameters:
            title (str): the title for the embed
            description (str): the description for the embed
            all_inline (bool): True if all fields should be added with inline=True
            **kwargs (dict): a set of keyword values to be displayed
        """
        embed = cls(title=title, description=description)
        for key, value in kwargs.items():
            embed.add_field(name=key, value=value, inline=all_inline)
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

        if len(name) > self.FIELD_NAME_TRIM:
            name = name[:self.FIELD_NAME_TRIM]
        if len(value) > self.FIELD_VALUE_TRIM:
            value = value[:self.FIELD_VALUE_TRIM]

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
