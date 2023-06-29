"""
This is a file to store the fake commands.Context object
"""


class MockContext:
    """
    This is the MockContext class

    Currently implemented variables and methods:
    channel -> The MockChannel object for the current context
    message -> The MockMessage in which the context was called with
    author -> The author of the command message
    """

    def __init__(self, channel=None, message=None, author=None):
        self.channel = channel
        self.message = message
        self.author = author
