"""
This is a file to store the fake disord.Bot objection
"""


class MockBot:
    """
    This is the MockBot class

    Currently implemented variables and methods:
    id -> An integer containing the ID of the bot
    """

    # pylint: disable=redefined-builtin
    def __init__(self, id=None):
        self.id = id
