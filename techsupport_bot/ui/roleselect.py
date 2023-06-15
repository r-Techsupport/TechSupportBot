import discord
from base import auxiliary


class RoleSelect(discord.ui.Select):
    def generate_options(self, roles):
        options = []
        for role in roles:
            options.append(discord.SelectOption(label=role))
        return options

    def __init__(self, role_list):
        super().__init__(
            placeholder="Select roles...",
            min_values=0,
            max_values=len(role_list),
            options=role_list,
        )

    async def callback(self, interaction: discord.Interaction):
        embed = auxiliary.prepare_confirm_embed(message=f"Selected: {self.values} roles")
        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )
        self.view.stop()


class SelectView(discord.ui.View):
    def __init__(self, role_list):
        super().__init__()
        # Adds the dropdown to our view object.
        self.select = RoleSelect(role_list)
        self.add_item(self.select)
