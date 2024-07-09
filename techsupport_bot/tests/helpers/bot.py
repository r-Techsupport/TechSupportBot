"""
This is a file to store the fake disord.Bot objection
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import helpers


class MockBot:
    """
    This is the MockBot class

    Functions implemented:
        get_prefix() -> returns a string of the bot prefix
        wait_until_ready() -> always returns true

    Args:
        input_id (int): An integer containing the ID of the bot
    """

    def __init__(self: Self, input_id: int = None) -> None:
        self.id = input_id

    async def get_prefix(self: Self, message: helpers.MockMessage = None) -> str:
        """A mock function to get the prefix of the bot

        Args:
            message (helpers.MockMessage): The message to lookup the prefix for
                based on the context (NOT CURRENTLY USED)

        Returns:
            str: The prefix, currently always "."
        """
        return "."

    def wait_until_ready(self: Self) -> bool:
        """A mock wait on ready function

        Returns:
            bool: Always true
        """
        return True
