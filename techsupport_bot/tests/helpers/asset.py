"""
This is a file to store the fake discord.Asset object
"""

from __future__ import annotations

from typing import Self


class MockAsset:
    """
    This is the MockAsset class

    Args:
        url (str): The URL associated with the asset
    """

    def __init__(self: Self, url: str = None) -> None:
        self.url = url
