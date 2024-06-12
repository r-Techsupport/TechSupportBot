import discord


class PersistentView(discord.ui.View):
    def __init__(self, test=None):
        self.test = test
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Yes, make changes",
        style=discord.ButtonStyle.green,
        custom_id="persistent_voting_view:yes",
    )
    async def green(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Voting")
        await cog.register_vote(interaction.user, self, interaction.message)
        await interaction.response.send_message("This is green.", ephemeral=True)

    @discord.ui.button(
        label="No, don't make changes",
        style=discord.ButtonStyle.red,
        custom_id="persistent_voting_view:no",
    )
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("This is red.", ephemeral=True)

    @discord.ui.button(
        label="Clear vote",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_voting_view:clear",
    )
    async def grey(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(interaction.message)
        await interaction.response.send_message("This is grey.", ephemeral=True)
