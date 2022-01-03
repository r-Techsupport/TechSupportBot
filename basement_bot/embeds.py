"""Module for builtin embeds.
"""

import discord


class SaneEmbed(discord.Embed):
    """An embed that is guaranteed to sanely handle validation constraints."""

    def trim(self, inp):
        """Returns a trimmed value.

        parameters:
            inp (str): the input value to trim
        """
        if not isinstance(inp, str):
            return inp
        return inp[:256]

    def trim_kwarg(self, kwargs, key):
        """Trims a specific kwarg.

        parameters:
            kwargs (dict): the kwargs to reference
            key (str): the kwargs key that maps to the trimmed value
        """
        kwargs[key] = self.trim(kwargs[key])

    def __setattr__(self, name, value):
        value = self.trim(value)
        return super().__setattr__(name, value)


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
