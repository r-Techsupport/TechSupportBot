"""
Module for the correct command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import configuration
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Correct plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Corrector(bot=bot))


class Corrector(cogs.BaseCog):
    """Class for the correct command for the discord bot."""

    @app_commands.command(
        name="correct",
        description="Replaces the text matching to_replace in the most recent matching message",
    )
    async def correct_command(
        self: Self, interaction: discord.Interaction, to_replace: str, replacement: str
    ) -> None:
        """This is the main processing for the correct command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            to_replace (str): What substring is being asked to find a message with
            replacement (str): If a message with to_replace is found,
                this is what it will be replaced with
        """

        prefix = configuration.get_config_entry(
            interaction.guild.id, "core_command_prefix"
        )
        message_to_correct = await auxiliary.search_channel_for_message(
            channel=interaction.channel,
            prefix=prefix,
            content_to_match=to_replace,
            allow_bot=False,
        )
        if not message_to_correct:
            embed = auxiliary.prepare_deny_embed(
                message="I couldn't find any message to correct"
            )
            await interaction.response.send_message(embed=embed)
            return

        updated_message = self.prepare_message(
            message_to_correct.content, to_replace, replacement
        )

        updated_message += " :white_check_mark:"

        if len(updated_message) > 4096:
            embed = auxiliary.prepare_deny_embed(
                message="The corrected message is too long to send"
            )
            await interaction.response.send_message(embed=embed)
            return

        if updated_message.count("\n") > 15:
            embed = auxiliary.prepare_deny_embed(
                message="The corrected message has too many lines to send",
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = auxiliary.generate_basic_embed(
            title="Correction!",
            description=updated_message,
            color=discord.Color.green(),
        )
        await interaction.response.send_message(
            embed=embed,
            content=auxiliary.construct_mention_string([message_to_correct.author]),
        )

    def prepare_message(
        self: Self, old_content: str, to_replace: str, replacement: str
    ) -> str:
        """This corrects a message based on input

        Args:
            old_content (str): The old content of the message to be corrected
            to_replace (str): What substring of the message needs to be replaced
            replacement (str): What string to replace to_replace with

        Returns:
            str: The corrected content
        """
        return old_content.replace(to_replace, f"**{replacement}**")
