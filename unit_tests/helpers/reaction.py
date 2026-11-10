"""
This is a file to store the fake discord.Message object
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import helpers


class MockReaction:
    """
    This is the MockReaction class

    Args:
        message (helpers.MockMessage): Last message a user had to add reactions to
        count (int): Number of reactions already on the message
    """

    def __init__(
        self: Self, message: helpers.MockMessage = None, count: int = None
    ) -> None:
        self.message = message
        self.count = count
