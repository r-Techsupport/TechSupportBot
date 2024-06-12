import discord


class PersistentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Yes, make changes",
        style=discord.ButtonStyle.green,
        custom_id="persistent_voting_view:yes",
    )
    async def green(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Voting")
        await cog.register_yes_vote(interaction, self)

    @discord.ui.button(
        label="No, don't make changes",
        style=discord.ButtonStyle.red,
        custom_id="persistent_voting_view:no",
    )
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Voting")
        await cog.register_no_vote(interaction, self)

    @discord.ui.button(
        label="Clear vote",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_voting_view:clear",
    )
    async def grey(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Voting")
        await cog.clear_vote(interaction, self)
