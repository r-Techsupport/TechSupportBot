"""
This is a file to store the fake disord.TextChannel objection
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import helpers


class MockChannel:
    """
    This is the MockChannel class

    Currently implemented variables and methods:
    message_history -> A list of MockMessage objects
    history() -> An async function to return history.
        A "limit" object may be passed, but is ignored in this implementation
    """

    def __init__(self: Self, history: list[helpers.MockMessage] = None) -> None:
        self.message_history = history

    async def history(self: Self, limit: int) -> AsyncGenerator[str, None]:
        """Replication of the async history method
        As history is not expected to be massive, this just yields every message

        Args:
            limit (int): The represents a limit. This is currently not used

        Yields:
            str: This represents a single message in the history
        """
        if limit == 0:
            return
        for message in self.message_history:
            yield message
