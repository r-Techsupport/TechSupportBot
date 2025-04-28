"""The file that holds the purge command"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs, extensionconfig, moderation
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="max_purge_amount",
        datatype="int",
        title="Max Purge Amount",
        description="The max amount of messages allowed to be purged in one command",
        default=50,
    )
    await bot.add_cog(Purger(bot=bot, extension_name="purge"))
    bot.add_extension_config("purge", config)


class Purger(cogs.BaseCog):
    """The class that holds the /purge command"""

    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.checks.bot_has_permissions(manage_messages=True)
    @app_commands.command(
        name="purge",
        description="Purge by pure duration of messages",
        extras={"module": "purge"},
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
        config = self.bot.guild_configs[str(interaction.guild.id)]

        if amount <= 0 or amount > config.extensions.purge.max_purge_amount.value:
            embed = auxiliary.prepare_deny_embed(
                message=f"Messages to purge must be between 0 and {config.extensions.purge.max_purge_amount.value}",
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
        await interaction.channel.purge(after=timestamp, limit=amount)

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=f"/purge amount: {amount}, duration: {duration_minutes}",
            guild=interaction.guild,
        )
