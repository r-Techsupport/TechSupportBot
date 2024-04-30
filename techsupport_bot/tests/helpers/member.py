"""
This is a file to store the fake discord.Member object
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import helpers


class MockMember:
    """
    This is the MockMember class

    Currently implemented variables and methods:
    id -> An integer containing the ID of the fake user
    bot -> Boolean stating if this member is a bot or not
    mention -> String that is just <@ID>
    name -> The string containing the users username
    display_avatar -> The MockAsset object for the avatar
    """

    def __init__(
        self: Self,
        input_id: int = None,
        bot: bool = False,
        name: str = None,
        display_avatar: helpers.MockAsset = None,
    ) -> None:
        self.id = input_id
        self.bot = bot
        self.mention = f"<@{input_id}>"
        self.name = name
        self.display_avatar = display_avatar
