import discord

from .application import Application


class AppNotice(discord.ui.View):
    async def send(self, channel: discord.abc.Messageable, message: str):
        embed = self.build_embed(message)
        await channel.send(embed=embed, view=self)

    def build_embed(self, message: str) -> discord.Embed:
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
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        """This declares the previous button, and what should happen when it's pressed"""
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
