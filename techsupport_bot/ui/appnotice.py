"""This contians the view for the periodic application notice to users"""

from __future__ import annotations

from typing import Self

import discord


class AppNotice(discord.ui.View):
    """The view containing a button and message encouraging users to apply

    Attrs:
        ICON (str): The Icon for the application reminder
    """

    ICON = "https://icon-icons.com/downloadimage.php?id=14692&root=80/PNG/256/&file=help_15418.png"

    async def send(self: Self, channel: discord.abc.Messageable, message: str) -> None:
        """The entry point to this function, will send a message to the given channel

        Args:
            channel (discord.abc.Messageable): The channel to send the message to
            message (str): The string message to be added as the embed description
        """
        embed = self.build_embed(message)
        await channel.send(embed=embed, view=self)

    def build_embed(self: Self, message: str) -> discord.Embed:
        """This builds the embed portion of the notification

        Args:
            message (str): The string message to be added as the embed description

        Returns:
            discord.Embed: The formatted embed ready to be send to users
        """
        embed = discord.Embed()
        embed.set_author(
            name="Volunteer interest form",
            icon_url=self.ICON,
        )
        embed.color = discord.Color.red()
        embed.description = message
        return embed

    @discord.ui.button(
        label="Apply Now",
        style=discord.ButtonStyle.primary,
        row=1,
        custom_id="application_button:only",
    )
    async def apply_button(
        self: Self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """This is what happens when the apply now button is pressed

        Args:
            interaction (discord.Interaction): The interaction that was
                generated when a user pressed the button
            button (discord.ui.Button): The button object created by this function
        """
        cog = interaction.client.get_cog("ApplicationManager")
        await cog.start_application(interaction)
