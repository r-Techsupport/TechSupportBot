"""
This is a file to store the fake discord.Asset object
"""


class MockAsset:
    """
    This is the MockAsset class

    Currently implemented variables and methods:
    url -> The URL associated with the asset
    """

    def __init__(self, url=None):
        self.url = url
