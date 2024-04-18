"""
This is a file to store the fake discord.Attachment object
"""

from __future__ import annotations

from typing import Self


class MockAttachment:
    """
    This is the MockAttachment class

    Currently implemented variables and methods:
    filename -> The string containing the name of the file
    """

    def __init__(self: Self, filename: str = None) -> None:
        self.filename = filename
