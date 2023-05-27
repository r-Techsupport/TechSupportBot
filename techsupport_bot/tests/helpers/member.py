"""
This is a file to store the fake discord.Member object
"""


class MockMember:
    """
    This is the MockMember class

    Currently implemented variables and methods:
    id -> An integer containing the ID of the fake user
    bot -> Boolean stating if this member is a bot or not
    """

    def __init__(self, id=None, bot=False):
        self.id = id
        self.bot = bot
