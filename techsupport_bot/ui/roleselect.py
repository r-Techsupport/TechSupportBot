import discord


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
        await interaction.response.send_message(
            f"You now have {self.values} roles", ephemeral=True
        )
        self.view.stop()


class SelectView(discord.ui.View):
    def __init__(self, role_list):
        super().__init__()
        # Adds the dropdown to our view object.
        self.select = RoleSelect(role_list)
        self.add_item(self.select)
