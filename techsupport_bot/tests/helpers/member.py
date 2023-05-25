"""
This is a file to store the fake discord.Member object
"""


class MockMember:
    """
    This is the MockMember class

    Currently implemented variables and methods:
    id -> An integer containing the ID of the fake user
    """

    # pylint: disable=redefined-builtin
    def __init__(self, id=None):
        self.id = id
