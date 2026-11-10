"""
This is a file to store the fake discord.Message object
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import helpers


class MockMessage:
    """
    This is the MockMessage class

    Args:
        content (str): The string containing the content of the message
        author (helpers.MockMember): The MockMember object who create the message
        attachments (list[helpers.MockAttachment]): A list of MockAttachment objects
        reactions (list[helpers.MockReaction]): A list of MockReaction objects
    """

    def __init__(
        self: Self,
        content: str = None,
        author: helpers.MockMember = None,
        attachments: list[helpers.MockAttachment] = None,
        reactions: list[helpers.MockReaction] = None,
    ) -> None:
        self.content = content
        self.author = author
        self.clean_content = content
        self.attachments = attachments
        self.reactions = reactions

    async def add_reaction(self: Self, reaction: list[helpers.MockReaction]) -> None:
        """Replication of the adding a reaction
        Adding reactions to a previous message

        Args:
           reaction (list[helpers.MockReaction]): An array of reactions on the message

        """
        self.reactions.append(reaction)
