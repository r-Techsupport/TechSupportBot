"""
This is a file to store the fake disord.Bot objection
"""


class MockBot:
    """
    This is the MockBot class

    Currently implemented variables and methods:
    id -> An integer containing the ID of the bot

    get_prefix() -> returns a string of the bot prefix
    wait_until_ready() -> always returns true
    """

    def __init__(self, id=None):
        self.id = id

    def get_prefix(self, message=None):
        """A mock function to get the prefix of the bot"""
        return "."

    def wait_until_ready(self):
        """A mock wait on ready function"""
        return True
