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

    Currently implemented variables and methods:
    id -> An integer containing the ID of the bot

    get_prefix() -> returns a string of the bot prefix
    wait_until_ready() -> always returns true
    """

    def __init__(self: Self, input_id: int = None) -> None:
        self.id = input_id

    async def get_prefix(self: Self, message: helpers.MockMessage = None) -> str:
        """A mock function to get the prefix of the bot"""
        return "."

    def wait_until_ready(self: Self) -> bool:
        """A mock wait on ready function"""
        return True
