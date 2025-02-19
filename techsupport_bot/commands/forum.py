"""The channel slowmode modification extension
Holds only a single slash command"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the slowmode cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(ForumChannel(bot=bot, extension_name="forum"))


class ForumChannel(cogs.BaseCog):
    """The cog that holds the slowmode commands and helper functions"""

    forum_group: app_commands.Group = app_commands.Group(
        name="forum", description="...", extras={"module": "forum"}
    )

    channel_id = "1288279278839926855"

    @forum_group.command(
        name="solved",
        description="Ban someone from making new applications",
        extras={"module": "forum"},
    )
    async def markSolved(self: Self, interaction: discord.Interaction) -> None:
        channel = await interaction.guild.fetch_channel(int(self.channel_id))
        if interaction.channel.parent == channel:
            if interaction.user != interaction.channel.owner:
                await interaction.response.send_message("You cannot do this")
                return
            await interaction.response.send_message("Marked as solved")
            await interaction.channel.edit(
                name=f"[SOLVED] {interaction.channel.name}"[:100],
                archived=True,
                locked=True,
            )

    @commands.Cog.listener()
    async def on_thread_create(self: Self, thread: discord.Thread) -> None:
        channel = await thread.guild.fetch_channel(int(self.channel_id))
        threads = channel.threads
        print(threads)
        if thread.parent == channel:
            await thread.send("HI")
