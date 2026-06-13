"""This module contains the /privacy command
This gives users the ability to get and read our privacy policy"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the privacy policy cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(PrivacyPolicy(bot=bot))


class PrivacyPolicy(cogs.BaseCog):
    """The cog that holds the privacy command, to let users see the privacy polciy"""

    @app_commands.command(
        name="privacy",
        description="Displays the link to the privacy policy",
        extras={"ephemeral_error": True, "always_enabled": True},
    )
    async def dataDeleteCommand(
        self: Self,
        interaction: discord.Interaction,
    ) -> None:
        """Shows users the configured privacy policy

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        policy_link = self.bot.file_config.bot_config.privacy_policy
        if not policy_link:
            embed = auxiliary.prepare_deny_embed(
                "It doesn't appear a privacy policy has been configured"
            )
        else:
            embed = auxiliary.prepare_confirm_embed(policy_link)

        await interaction.response.send_message(embed=embed, ephemeral=True)
