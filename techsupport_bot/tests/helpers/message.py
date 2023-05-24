"""
This is a file to store the fake discord.Message object
"""


class MockMessage:
    """
    This is the MockMessage class

    Currently implemented variables and methods:
    content -> The string containing the content of the message
    author -> The MockMember object who create the message
    """

    def __init__(self, content=None, author=None):
        self.content = content
        self.author = author
