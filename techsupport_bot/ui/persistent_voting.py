"""This holds the few buttons needed for voting, configured to be persistent"""

import discord


class VotingButtonPersistent(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Yes, make changes",
        style=discord.ButtonStyle.green,
        custom_id="persistent_voting_view:yes",
    )
    async def yes_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """The button that is for voting yes.
        Calls the yes function in the main commands/voting.py file

        Args:
            interaction (discord.Interaction): The interaction created when the button was pressed
            button (discord.ui.Button): The button object itself
        """
        cog = interaction.client.get_cog("Voting")
        await cog.register_yes_vote(interaction, self)

    @discord.ui.button(
        label="No, don't make changes",
        style=discord.ButtonStyle.red,
        custom_id="persistent_voting_view:no",
    )
    async def no_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """The button that is for voting no.
        Calls the no function in the main commands/voting.py file

        Args:
            interaction (discord.Interaction): The interaction created when the button was pressed
            button (discord.ui.Button): The button object itself
        """
        cog = interaction.client.get_cog("Voting")
        await cog.register_no_vote(interaction, self)

    @discord.ui.button(
        label="Clear vote",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_voting_view:clear",
    )
    async def clear_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """The button that is for voting clear.
        Calls the clear function in the main commands/voting.py file

        Args:
            interaction (discord.Interaction): The interaction created when the button was pressed
            button (discord.ui.Button): The button object itself
        """
        cog = interaction.client.get_cog("Voting")
        await cog.clear_vote(interaction, self)
