"""This holds the UI view used by the role extension"""

from __future__ import annotations

from typing import Self

import discord


class RoleSelect(discord.ui.Select):
    """This holds the select object for a list of roles

    Args:
        role_list (list[str]): A list of SelectOption to be in the dropdown
    """

    def __init__(self: Self, role_list: list[str]) -> None:
        super().__init__(
            placeholder="Select roles...",
            min_values=0,
            max_values=len(role_list),
            options=role_list,
        )
        self.timeout = False

    async def callback(self: Self, interaction: discord.Interaction) -> None:
        """What happens when the select menu has been used

        Args:
            interaction (discord.Interaction): The interaction that called this select object
        """
        self.view.stop()

    async def on_timeout(self: Self) -> None:
        """What happens when the view timesout. This is to prevent all roles from being removed."""
        self.values = None
        self.timeout = True
        self.view.stop()


class SelectView(discord.ui.View):
    """This is the view that will hold only the dropdown
    Adds the dropdown and does nothing else
    Args:
        role_list (list[str]): The list of SelectOptions to add to the dropdown
    """

    def __init__(self: Self, role_list: list[str]) -> None:
        super().__init__()
        # Adds the dropdown to our view object.
        self.select = RoleSelect(role_list)
        self.add_item(self.select)
