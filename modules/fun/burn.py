"""
Module for the burn command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import configuration
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Burn plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Burn(bot=bot))


class Burn(cogs.BaseCog):
    """Class for Burn command on the discord bot.

    Attributes:
        PHRASES (list[str]): The list of phrases to pick from
    """

    PHRASES: list[str] = [
        "Sick BURN!",
        "Someone is going to need ointment for that BURN!",
        "Fire! Call 911! Someone just got BURNED!",
        "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOH BURN!",
        "BURN ALERT!",
        "Was that message a hot pan? BECAUSE IT BURNS!",
    ]

    @app_commands.command(
        name="burn",
        description="Declares mentioned user's message as a BURN!",
    )
    async def burn(
        self: Self, interaction: discord.Interaction, user_to_burn: discord.Member
    ) -> None:
        """The only purpose of this function is to accept input from discord

        Args:
            interaction (discord.Interaction): The interaction which called this command
            user_to_burn (discord.Member): The user in which to burn
        """
        prefix = configuration.get_config_entry(
            interaction.guild.id, "core_command_prefix"
        )
        message = await auxiliary.search_channel_for_message(
            channel=interaction.channel, prefix=prefix, member_to_match=user_to_burn
        )

        if not message:
            embed = auxiliary.prepare_deny_embed(
                message="I could not a find a message to reply to"
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = auxiliary.generate_basic_embed(
            title="Burn Alert!",
            description=f"🔥🔥🔥 {random.choice(self.PHRASES)} 🔥🔥🔥",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(
            content=auxiliary.construct_mention_string([user_to_burn]),
            embed=embed,
            ephemeral=False,
        )

        await auxiliary.add_list_of_reactions(
            message=message, reactions=["🔥", "🚒", "👨‍🚒"]
        )
