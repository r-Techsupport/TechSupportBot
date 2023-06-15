"""This holds the UI view used by the role extension"""
import discord
from base import auxiliary


class RoleSelect(discord.ui.Select):
    """This holds the select object for a list of roles"""

    def __init__(self, role_list):
        """A function to set some defaults

        Args:
            role_list (list): A list of SelectOption to be in the dropdown
        """
        super().__init__(
            placeholder="Select roles...",
            min_values=0,
            max_values=len(role_list),
            options=role_list,
        )

    async def callback(self, interaction: discord.Interaction):
        """What happens when the select menu has been used

        Args:
            interaction (discord.Interaction): The interaction that called this select object
        """
        embed = auxiliary.prepare_confirm_embed(
            message=f"Selected: {self.values} roles"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.view.stop()


class SelectView(discord.ui.View):
    """This is the view that will hold only the dropdown"""

    def __init__(self, role_list):
        """Adds the dropdown and does nothing else

        Args:
            role_list (list): The list of SelectOptions to add to the dropdown
        """
        super().__init__()
        # Adds the dropdown to our view object.
        self.select = RoleSelect(role_list)
        self.add_item(self.select)
