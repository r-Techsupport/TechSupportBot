"""The report command"""

from typing import Self

import discord


class Report:
    """The class that holds the report command and helper function"""

    async def report_command(
        self: Self, interaction: discord.Interaction, report_str: str
    ) -> None:
        """This is the core of the /report command
        Allows users to report potential moderation issues to staff

        Args:
            self (Self): _description_
            interaction (discord.Interaction): The interaction that called this command
            report_str (str): The report string that the user submitted
        """
