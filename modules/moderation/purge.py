"""The file that holds the purge command"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import configuration
from core import auxiliary, cogs, moderation
from modules.moderation import modlog

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(Purger(bot=bot))


class Purger(cogs.BaseCog):
    """The class that holds the /purge command"""

    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command(
        name="purge",
        description="Purge by pure duration of messages",
    )
    async def purge_command(
        self: Self,
        interaction: discord.Interaction,
        amount: int,
        duration_minutes: int = None,
    ) -> None:
        """The core purge command that can purge by either amount or duration

        Args:
            interaction (discord.Interaction): The interaction that called this command
            amount (int): The max amount of messages to purge
            duration_minutes (int, optional): The max age of a message to purge. Defaults to None.
        """
        max_purge_amount = configuration.get_config_entry(
            interaction.guild.id, "purge_max_purge_amount"
        )

        if amount <= 0 or amount > max_purge_amount:
            embed = auxiliary.prepare_deny_embed(
                message=(
                    "Messages to purge must be between 1 " f"and {max_purge_amount}"
                ),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if duration_minutes and duration_minutes < 0:
            embed = auxiliary.prepare_deny_embed(
                message="Message age must be older than 0 minutes",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if duration_minutes:
            timestamp = datetime.datetime.utcnow() - datetime.timedelta(
                minutes=duration_minutes
            )
        else:
            timestamp = None

        await interaction.response.send_message("Purge Successful", ephemeral=True)
        sent_message = await interaction.original_response()
        deleted = await interaction.channel.purge(after=timestamp, limit=amount)
        await modlog.log_action(
            bot=self.bot,
            action_type="purge",
            guild=interaction.guild,
            moderator=interaction.user,
        )
        await interaction.followup.edit_message(
            message_id=sent_message.id,
            content=f"Purge Successful. Deleted {len(deleted)} messages.",
        )
