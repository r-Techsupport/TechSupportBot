"""This contians the view for the periodic application notice to users"""
import discord

from .application import Application


class AppNotice(discord.ui.View):
    """The view containing a button and message encouraging users to apply"""

    async def send(self, channel: discord.abc.Messageable, message: str) -> None:
        """The entry point to this function, will send a message to the given channel

        Args:
            channel (discord.abc.Messageable): The channel to send the message to
            message (str): The string message to be added as the embed description
        """
        embed = self.build_embed(message)
        await channel.send(embed=embed, view=self)

    def build_embed(self, message: str) -> discord.Embed:
        """This builds the embed portion of the notification

        Args:
            message (str): The string message to be added as the embed description

        Returns:
            discord.Embed: The formatted embed ready to be send to users
        """
        embed = discord.Embed()
        embed.set_author(
            name="Volunteer interest form",
            icon_url="https://icon-icons.com/downloadimage.php?id=14692&root=80/PNG/256/&file=help_15418.png",
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
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """This is what happens when the apply now button is pressed

        Args:
            interaction (discord.Interaction): The interaction that was generated when a user pressed the button
            button (discord.ui.Button): The button object created by this function
        """
        cog = interaction.client.get_cog("ApplicationManager")
        can_apply = await cog.check_if_can_apply(interaction.user)
        if not can_apply:
            await interaction.response.send_message(
                "You are not eligible to apply right now. Ask the server moderators if"
                " you have questions",
                ephemeral=True,
            )
            return

        form = Application()
        await interaction.response.send_modal(form)
        await form.wait()
        cog = interaction.client.get_cog("ApplicationManager")
        if not cog:
            print("ERROR")
            return
        await cog.handle_new_application(
            interaction.user, form.background.value, form.reason.value
        )
