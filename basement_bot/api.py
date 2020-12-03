"""Provides a basic bot interface for building more advanced ones.
"""

# pylint: disable=too-few-public-methods
class BotAPI:
    """Base bot API.

    parameters:
        bot (BasementBot): the bot object
    """

    def __init__(self, bot):
        self.bot = bot
