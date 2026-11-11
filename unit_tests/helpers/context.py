"""
This is a file to store the fake commands.Context object
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import helpers


class MockContext:
    """
    This is the MockContext class

    Args:
        channel (helpers.MockChannel): The MockChannel object for the current context
        message (helpers.MockMessage): The MockMessage in which the context was called with
        author (helpers.MockMember): The author of the command message
    """

    def __init__(
        self: Self,
        channel: helpers.MockChannel = None,
        message: helpers.MockMessage = None,
        author: helpers.MockMember = None,
    ) -> None:
        self.channel = channel
        self.message = message
        self.author = author
