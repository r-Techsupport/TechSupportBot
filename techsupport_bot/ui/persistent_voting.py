"""This holds the few buttons needed for voting, configured to be persistent"""

from typing import Self

import discord


class VotingButtonPersistent(discord.ui.View):
    """This is designed to be used when running a vote
    These buttons will work even after a reboot of the bot
    """

    def __init__(self: Self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Yes, make changes",
        style=discord.ButtonStyle.green,
        custom_id="persistent_voting_view:yes",
    )
    async def yes_button(
        self: Self, interaction: discord.Interaction, button: discord.ui.Button
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
        label="Abstain from voting",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent_voting_view:abstain",
        row=1,
    )
    async def abstain_button(
        self: Self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """The button that is for voting yes.
        Calls the yes function in the main commands/voting.py file

        Args:
            interaction (discord.Interaction): The interaction created when the button was pressed
            button (discord.ui.Button): The button object itself
        """
        cog = interaction.client.get_cog("Voting")
        await cog.register_abstain_vote(interaction, self)

    @discord.ui.button(
        label="No, don't make changes",
        style=discord.ButtonStyle.red,
        custom_id="persistent_voting_view:no",
        row=0,
    )
    async def no_button(
        self: Self, interaction: discord.Interaction, button: discord.ui.Button
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
        label="Remove your vote",
        style=discord.ButtonStyle.grey,
        custom_id="persistent_voting_view:clear",
        row=1,
    )
    async def clear_button(
        self: Self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """The button that is for voting clear.
        Calls the clear function in the main commands/voting.py file

        Args:
            interaction (discord.Interaction): The interaction created when the button was pressed
            button (discord.ui.Button): The button object itself
        """
        cog = interaction.client.get_cog("Voting")
        await cog.clear_vote(interaction, self)
