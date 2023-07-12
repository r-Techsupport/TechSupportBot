"""A class to handle the confirm request"""
from enum import Enum, auto

import discord
from base import auxiliary


class ConfirmResponse(Enum):
    """A class to define the 3 responses
    CONFIRMED - The original author clicked the "confirm" button
    DENIED - The original author clicked the "cancel" button
    TIMEOUT - No buttons were pressed in the timeout range
    """

    CONFIRMED = auto()
    DENIED = auto()
    TIMEOUT = auto()


class Confirm(discord.ui.View):
    """The class that holds the view for the confirm

    The entry point for this class is the send function
    Don't call anything else
    """

    def __init__(self):
        super().__init__()
        self.value = (
            ConfirmResponse.TIMEOUT
        )  # default to timeout unless a button is pressed

    async def send(
        self,
        message: str,
        channel: discord.abc.Messageable,
        author: discord.Member,
        timeout: int = 60,
        interaction: discord.Interaction | None = None,
        ephemeral: bool = False,
    ) -> None:
        """A function initiate the confirm view

        Args:
            message (str): The message to ask the user if they want to confirm
            channel (discord.abc.Messageable): The channel this should be sent in
            author (discord.Member): The original author of the command triggering this
            timeout (int, optional): The amount of seconds to wait for a response before
                returning ConfirmResponse.TIMEOUT. Defaults to 60.
        """
        embed = auxiliary.generate_basic_embed(
            title="Please confirm!", description=message, color=discord.Color.green()
        )
        if interaction:
            self.followup = interaction.followup
            self.message = await self.followup.send(
                content=author.mention, embed=embed, view=self, ephemeral=ephemeral
            )
        else:
            self.message = await channel.send(
                content=author.mention, embed=embed, view=self
            )

        self.author = author
        self.timeout = timeout

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Define what happens when the confirm button is pressed"""
        await interaction.response.defer()
        self.value = ConfirmResponse.CONFIRMED
        await self.message.delete()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Define what happens when the cancel button is pressed"""
        await interaction.response.defer()
        self.value = ConfirmResponse.DENIED
        await self.message.delete()
        self.stop()

    async def on_timeout(self):
        """This deletes the buttons after the timeout has elapsed"""
        await self.message.delete()

    async def interaction_check(self, interaction):
        """This checks to ensure that only the original author can press the button
        If the original author didn't press, it sends an ephemeral message
        """
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Only the original author can control this!", ephemeral=True
            )
            return False
        return True
