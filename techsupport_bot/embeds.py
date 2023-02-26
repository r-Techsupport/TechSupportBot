"""Module for builtin embeds.
"""

import discord


class ConfirmEmbed(discord.Embed):
    """An embed for confirmation responses.

    parameters:
        message (str): the response message
    """

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        super().__init__(*args, **kwargs)
        self.title = "😄 👍"
        self.description = message
        self.color = discord.Color.green()


class DenyEmbed(discord.Embed):
    """An embed for deny responses.

    parameters:
        message (str): the response message
    """

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        super().__init__(*args, **kwargs)
        self.title = "😕 👎"
        self.description = message
        self.color = discord.Color.red()
