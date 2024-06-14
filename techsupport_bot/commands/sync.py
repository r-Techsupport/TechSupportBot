"""
Commands which allows the app command tree to be updated
The cog in the file is named:
    AppCommandSync

This file contains 1 commands:
    .sync
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Sync plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(AppCommandSync(bot=bot))


class AppCommandSync(cogs.BaseCog):
    """
    The class that holds the sync command
    """

    sync = app_commands.Group(
        name="sync", description="Group for all sync app commands"
    )

    @commands.check(auxiliary.bot_admin_check_context)
    @auxiliary.with_typing
    @commands.command(
        name="sync",
        description="Syncs slash commands",
        usage="",
    )
    async def sync_slash_commands(self: Self, ctx: commands.Context) -> None:
        """A simple command to manually sync slash commands

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        message = await self.sync_command_tree()
        await auxiliary.send_confirm_embed(
            message=message,
            channel=ctx.channel,
        )

    async def sync_command_tree(self: Self) -> str:
        old = await self.bot.tree.fetch_commands()
        synced = await self.bot.tree.sync()
        removed_items = [item.mention for item in old if item not in synced]
        added_items = [item.mention for item in synced if item not in old]
        message = (
            "Successfully updated the slash command tree. Currently there are"
            f" {len(synced)} commands in the tree.\nAdded items: {added_items}."
            f"\nRemoved items: {removed_items}"
        )
        return message

    @commands.check(auxiliary.bot_admin_check_interaction)
    @sync.command(
        name="update",
        description="Syncs the command tree on demand",
        extras={
            "module": "sync",
        },
    )
    async def sync_app_command_version(
        self: Self, interaction: discord.Interaction
    ) -> None:
        await interaction.response.send_message(content="Updating tree", ephemeral=True)
        message = await self.sync_command_tree()
        embed = auxiliary.prepare_confirm_embed(
            message=message,
        )
        # For some reason this is an unknown interaction on every run except the very first
        # Ghosts
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.check(auxiliary.bot_admin_check_interaction)
    @sync.command(
        name="list",
        description="Lists all commands in the command tree",
        extras={
            "module": "sync",
        },
    )
    async def sync_app_command_version(
        self: Self, interaction: discord.Interaction
    ) -> None:
        command_tree = await self.bot.tree.fetch_commands()
        list = "\n".join([command.mention for command in command_tree])
        embed = auxiliary.prepare_confirm_embed(
            message=list,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
