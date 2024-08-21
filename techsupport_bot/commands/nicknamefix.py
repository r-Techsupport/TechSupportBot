"""This holds a command to manually adjust someones nickname
Uses the same filter as the automatic nickname filter"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands
from functions import nickname

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the nicknamefixer cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(NicknameFixer(bot=bot))


class NicknameFixer(cogs.BaseCog):
    """The class that holds the nickname fixer"""

    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.command(
        name="nicknamefix",
        description="Auto adjusts a nickname of the given member",
        extras={
            "usage": "member",
            "module": "nicknamefix",
        },
    )
    async def fixnickname(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Manually adjusts someones nickname to comply with the nickname filter
        Does not send a DM

        Args:
            interaction (discord.Interaction): The interaction the command was called at
            member (discord.Member): The member to update the nickname for
        """
        if member.bot:
            embed = auxiliary.prepare_deny_embed("Bots don't get new nicknames")
            return
        new_nickname = nickname.format_username(member.display_name)
        if new_nickname == member.display_name:
            embed = auxiliary.prepare_deny_embed(
                f"{member.mention} doesn't need a new nickname"
            )
            await interaction.response.send_message(embed=embed)
            return
        await member.edit(
            nick=new_nickname,
            reason=f"Change nickname command, ran by {interaction.user}",
        )
        embed = auxiliary.prepare_confirm_embed(
            f"{member.mention} name changed to {new_nickname}"
        )
        await interaction.response.send_message(embed=embed)
        return
