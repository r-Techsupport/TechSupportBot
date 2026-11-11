"""A class to handle the confirm request"""

from __future__ import annotations

from enum import Enum, auto
from typing import Self

import discord

from core import auxiliary


class ConfirmResponse(Enum):
    """A class to define the 3 responses

    Attributes:
        CONFIRMED (int): The original author clicked the "confirm" button
        DENIED (int): The original author clicked the "cancel" button
        TIMEOUT (int): No buttons were pressed in the timeout range
    """

    CONFIRMED: int = auto()
    DENIED: int = auto()
    TIMEOUT: int = auto()


class Confirm(discord.ui.View):
    """The class that holds the view for the confirm

    Call send to show the confirmation. Use message.edit to update its message.
    """

    def __init__(self: Self) -> None:
        super().__init__()
        # default to timeout unless a button is pressed
        self.value = ConfirmResponse.TIMEOUT

    async def send(
        self: Self,
        interaction: discord.Interaction,
        message: str,
        timeout: int = 60,
        ephemeral: bool = False,
    ) -> None:
        """A function initiate the confirm view

        Args:
            interaction (discord.Interaction): The interaction to reply or follow up to
            message (str): The message to ask the user if they want to confirm
            timeout (int, optional): The amount of seconds to wait for a response before returning ConfirmResponse.TIMEOUT. Defaults to 60.
            ephemeral (bool, optional): Whether the confirmation should be private. Defaults to False.
        """
        embed = auxiliary.generate_basic_embed(
            title="Please confirm!", description=message, color=discord.Color.green()
        )
        self.interaction: discord.Interaction = interaction
        self.timeout: int = timeout

        if interaction.response.is_done():
            self.message = await interaction.followup.send(
                embed=embed, view=self, ephemeral=ephemeral
            )
        else:
            await interaction.response.send_message(
                embed=embed, view=self, ephemeral=ephemeral
            )
            self.message = await interaction.original_response()

    async def delete_buttons(self: Self) -> None:
        await self.message.edit(view=None)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self: Self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Define what happens when the confirm button is pressed

        Args:
            interaction (discord.Interaction): The interaction generated when the button pressed
            button (discord.ui.Button): The button object that got pressed
        """
        await interaction.response.defer()
        self.value = ConfirmResponse.CONFIRMED
        await self.delete_buttons()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(
        self: Self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Define what happens when the cancel button is pressed

        Args:
            interaction (discord.Interaction): The interaction generated when the button pressed
            button (discord.ui.Button): The button object that got pressed
        """
        await interaction.response.defer()
        self.value = ConfirmResponse.DENIED
        await self.delete_buttons()
        self.stop()

    async def on_timeout(self: Self) -> None:
        """Disable the buttons after the timeout has elapsed."""
        for child in self.walk_children():
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self: Self, interaction: discord.Interaction) -> bool:
        """This checks to ensure that only the original author can press the button
        If the original author didn't press, it sends an ephemeral message

        Args:
            interaction (discord.Interaction): The interaction generated when this UI is interacted with in any way

        Returns:
            bool: If this is False the interaction should not be followed through with
        """
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "Only the original author can control this!", ephemeral=True
            )
            return False
        return True
