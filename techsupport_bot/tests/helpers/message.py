"""
This is a file to store the fake discord.Message object
"""


class MockMessage:
    """
    This is the MockMessage class

    Currently implemented variables and methods:
    content -> The string containing the content of the message
    author -> The MockMember object who create the message
    attachments -> A list of MockAttacment objects
    """

    def __init__(self, content=None, author=None, attachments=None):
        self.content = content
        self.author = author
        self.attachments = attachments
