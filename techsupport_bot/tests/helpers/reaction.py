"""
This is a file to store the fake discord.Message object
"""


class MockReaction:
    """
    This is the MockReaction class

    Currently implemented variables and methods:
    message -> Last message a user had to add reactions to
    count -> Number of reactions already on the message
    """

    def __init__(self, message=None, count=None):
        self.message = message
        self.count = count
