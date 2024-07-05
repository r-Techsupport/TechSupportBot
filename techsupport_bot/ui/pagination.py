"""This is a file to house the class for the pagination view
This allows unlimited pages to be scrolled through"""

from __future__ import annotations

from typing import Self

import discord


class PaginateView(discord.ui.View):
    """The custom paginate view class
    This holds all the buttons and how the pages should work.

    To use this, call the send function. Everything else is automatic

    Attrs:
        current_page (int): The current page number the user is on
        data (list[str | discord.Embed]): The list of data for the pages
        timeout (int): The timeout till the buttons dissapear without interaction
        message (discord.Message): The message that has the pagination
    """

    current_page: int = 1
    data = None
    timeout = 120
    message = ""

    def add_page_numbers(self: Self) -> None:
        """A simple function to add page numbers to embed footer"""
        for index, embed in enumerate(self.data):
            if isinstance(embed, discord.Embed):
                embed.set_footer(text=f"Page {index+1} of {len(self.data)}")

    async def send(
        self: Self,
        channel: discord.abc.Messageable,
        author: discord.Member,
        data: list[str | discord.Embed],
        interaction: discord.Interaction | None = None,
    ) -> None:
        """Entry point for PaginateView

        Args:
            channel (discord.abc.Messageable): The channel to send the pages to
            author (discord.Member): The author of the pages command
            data (list[str | discord.Embed]): A list of pages in order
                with [0] being the first page
            interaction (discord.Interaction | None): The interaction this
                should followup with (Optional)
        """
        self.author = author
        self.data = data
        self.update_buttons()
        if isinstance(self.data[0], discord.Embed):
            self.add_page_numbers()

        if interaction:
            self.followup = interaction.followup
            self.message = await self.followup.send(view=self)
        else:
            self.message = await channel.send(view=self)

        if len(self.data) == 1:
            self.remove_item(self.prev_button)
            self.remove_item(self.next_button)
        await self.update_message()

    async def update_message(self: Self) -> None:
        """The redraws the message with the new page"""
        self.update_buttons()
        if isinstance(self.data[self.current_page - 1], discord.Embed):
            await self.message.edit(embed=self.data[self.current_page - 1], view=self)
        else:
            await self.message.edit(content=self.data[self.current_page - 1], view=self)

    def update_buttons(self: Self) -> None:
        """This disables buttons if there are no more pages forward/backward"""
        if self.current_page == 1:
            self.prev_button.disabled = True
            self.prev_button.style = discord.ButtonStyle.gray
        else:
            self.prev_button.disabled = False
            self.prev_button.style = discord.ButtonStyle.primary

        if self.current_page == len(self.data):
            self.next_button.disabled = True
            self.next_button.style = discord.ButtonStyle.gray
        else:
            self.next_button.disabled = False
            self.next_button.style = discord.ButtonStyle.primary

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary, row=1)
    async def prev_button(
        self: Self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        """This declares the previous button, and what should happen when it's pressed

        Args:
            interaction (discord.Interaction): The interaction generated when the button pressed
        """
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_message()

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary, row=1)
    async def next_button(
        self: Self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        """This declares the next button, and what should happen when it's pressed

        Args:
            interaction (discord.Interaction): The interaction generated when the button pressed
        """
        await interaction.response.defer()
        self.current_page += 1
        await self.update_message()

    @discord.ui.button(emoji="🛑", style=discord.ButtonStyle.danger, row=1)
    async def stop_button(
        self: Self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        """This declares the stop button, and what should happen when it's pressed

        Args:
            interaction (discord.Interaction): The interaction generated when the button pressed
        """
        await interaction.response.defer()
        self.clear_items()
        self.stop()
        await self.update_message()

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def trash_button(
        self: Self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        """This declares the trash button, and what should happen when it's pressed

        Args:
            interaction (discord.Interaction): The interaction generated when the button pressed
        """
        await interaction.response.defer()
        self.stop()
        await self.message.delete()

    async def interaction_check(self: Self, interaction: discord.Interaction) -> bool:
        """This checks to ensure that only the original author can press the button
        If the original author didn't press, it sends an ephemeral message

        Args:
            interaction (discord.Interaction): The interaction generated when this
                UI is interacted with in any way

        Returns:
            bool: If this is False the interaction should NOT be followed through with

        """
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Only the original author can control this!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self: Self) -> None:
        """This deletes the buttons after the timeout has elapsed"""
        self.clear_items()
        await self.update_message()
