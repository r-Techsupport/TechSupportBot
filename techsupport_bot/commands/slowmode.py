"""The channel slowmode modification extension
Holds only a single slash command"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the slowmode cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(SlowmodeManager(bot=bot))


class SlowmodeManager(cogs.BaseCog):
    """The cog that holds the slowmode commands and helper functions"""

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.command(
        name="slowmode",
        description="Modifies slowmode on a given channel",
        extras={
            "brief": "Changes time for slowmode",
            "usage": "seconds, [optional] channel",
            "module": "slowmode",
        },
    )
    async def slowmode(
        self: Self,
        interaction: discord.Interaction,
        seconds: int,
        channel: discord.abc.GuildChannel = None,
    ) -> None:
        """Modifies slowmode on a given channel

        Args:
            interaction (discord.Interaction): The interaction that called this command
            seconds (int): The seconds to change the slowmode to. 0 will disable slowmode
            channel (discord.abc.GuildChannel, optional): If specified, the channel to modify
                slowmode on. Defaults to the channel the command was invoked in.
        """
        if seconds > 21600 or seconds < 0:
            embed = auxiliary.prepare_deny_embed(
                "Slowmode must be between 0 and 21600 seconds"
            )
            await interaction.response.send_message(embed=embed)
            return

        if not channel:
            channel = interaction.channel
        await channel.edit(slowmode_delay=seconds)
        embed = auxiliary.prepare_confirm_embed(
            f"Slowmode successfully modified in channel {channel.mention} to"
            f" {seconds} seconds"
        )
        await interaction.response.send_message(embed=embed)
