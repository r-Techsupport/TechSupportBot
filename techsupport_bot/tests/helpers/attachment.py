"""
This is a file to store the fake discord.Attachment object
"""


class MockAttachment:
    """
    This is the MockAttachment class

    Currently implemented variables and methods:
    filename -> The string containing the name of the file
    """

    def __init__(self, filename=None):
        self.filename = filename
