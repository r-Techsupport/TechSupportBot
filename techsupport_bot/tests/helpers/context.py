"""
This is a file to store the fake commands.Context object
"""


class MockContext:
    """
    This is the MockContext class

    Currently implemented variables and methods:
    channel -> The MockChannel object for the current context
    """

    def __init__(self, channel=None):
        self.channel = channel
