"""The user data deletion extension
Holds only a single slash command"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import ui
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the data delete cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(DataDeleter(bot=bot))


class DataDeleter(cogs.BaseCog):
    """The cog that holds the data delete commands and helper functions"""

    @app_commands.command(
        name="data_delete",
        description="Deletes your data from the databases in the bot",
        extras={
            "ephemeral_error": True,
        },
    )
    async def dataDeleteCommand(
        self: Self,
        interaction: discord.Interaction,
    ) -> None:
        """Prompts users to delete their own data

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        # Search application, duck, grab, XP for user
        delete_message = (
            "This will delete all of the following information **across all servers**:\n"
            "- Any applications you have submitted, including the history of those applications\n"
            "- Duck hunt participation, including speed records and kill/friend counts\n"
            "- All grabs of your messages, including those grabbed by other users\n"
            "- XP data, including losing access to your XP roles\n\n"
            "**This action is irreversible!**"
        )
        await interaction.response.defer(ephemeral=True)
        view = ui.Confirm()
        await view.send(
            message=delete_message,
            channel=interaction.channel,
            author=interaction.user,
            interaction=interaction,
            ephemeral=True,
        )
        await view.wait()

        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            embed = auxiliary.prepare_deny_embed(message=f"Your data was not deleted")
            await view.followup.send(embed=embed, ephemeral=True)
            return

        records_deleted = 0
        application_database = await self.bot.models.Applications.query.where(
            self.bot.models.Applications.applicant_id == str(interaction.user.id)
        ).gino.all()
        for entry in application_database:
            await entry.delete()
            records_deleted += 1

        duck_database = await self.bot.models.DuckUser.query.where(
            self.bot.models.DuckUser.author_id == str(interaction.user.id)
        ).gino.all()
        for entry in duck_database:
            await entry.delete()
            records_deleted += 1

        grab_database = await self.bot.models.Grab.query.where(
            self.bot.models.Grab.author_id == str(interaction.user.id)
        ).gino.all()
        for entry in grab_database:
            await entry.delete()
            records_deleted += 1

        xp_database = await self.bot.models.XP.query.where(
            self.bot.models.XP.user_id == str(interaction.user.id)
        ).gino.all()
        for entry in xp_database:
            await entry.delete()
            records_deleted += 1

        embed = auxiliary.prepare_confirm_embed(
            f"Successfully deleted {records_deleted} entries from the database"
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
