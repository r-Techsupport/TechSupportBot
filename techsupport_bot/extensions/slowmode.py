from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from base import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot):
    await bot.add_cog(SlowmodeManager(bot=bot))


class SlowmodeManager(cogs.BaseCog):
    @app_commands.command(
        name="slowmode",
        description="Modifies slowmode on a given channel",
        extras={
            "brief": "Changes time for slowmode",
            "usage": "seconds, [optional] channel",
        },
    )
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: int,
        channel: discord.abc.GuildChannel = None,
    ):
        if seconds > 216000 or seconds < 0:
            embed = auxiliary.prepare_deny_embed(
                "Slowmode must be between 0 and 21600 seconds"
            )
            await interaction.response.send_message(embed=embed)
            return

        if not channel:
            channel = interaction.channel
        await channel.edit(slowmode_delay=seconds)
        embed = auxiliary.prepare_confirm_embed(
            f"Slowmode successfully modified in channel {channel.mention} to {seconds} seconds"
        )
        await interaction.response.send_message(embed=embed)
