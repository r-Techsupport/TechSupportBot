""" ""The channel slowmode modification extension
Holds only a single slash command"""

from __future__ import annotations

import re
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
    disallowed_title_patterns = [
        re.compile(
            r"^(?:I)?(?:\s)?(?:need|please I need|please|pls|plz)?(?:\s)?help(?:\s)?(?:me|please)?(?:\?|!)?$",
            re.IGNORECASE,
        ),
        re.compile(r"^\S+$"),  # Very short single-word titles
        re.compile(
            r"\b(it('?s)? not working|not working|issue|problem|error)\b", re.IGNORECASE
        ),
        re.compile(r"\b(urgent|ASAP|quick help|fast)\b", re.IGNORECASE),
        re.compile(r"[!?]{3,}"),  # Titles with excessive punctuation
    ]

    disallowed_body_patterns = [
        re.compile(r"^.{0,14}$"),  # Bodies shorter than 15 characters
        re.compile(r"^(\[[^\]]*\])?https?://\S+$"),  # Only links in the body
    ]

    @forum_group.command(
        name="solved",
        description="Ban someone from making new applications",
        extras={"module": "forum"},
    )
    async def markSolved(self: Self, interaction: discord.Interaction) -> None:
        channel = await interaction.guild.fetch_channel(int(self.channel_id))
        if interaction.channel.parent == channel:
            if interaction.user != interaction.channel.owner:
                embed = discord.Embed(
                    title="Permission Denied",
                    description="You cannot do this",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed)
                return
            embed = discord.Embed(
                title="Thread Marked as Solved",
                description="This thread has been archived and locked.",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed)
            await interaction.channel.edit(
                name=f"[SOLVED] {interaction.channel.name}"[:100],
                archived=True,
                locked=True,
            )

    @commands.Cog.listener()
    async def on_thread_create(self: Self, thread: discord.Thread) -> None:
        channel = await thread.guild.fetch_channel(int(self.channel_id))
        if thread.parent != channel:
            return

        embed = discord.Embed(
            title="Thread Rejected",
            description="Your thread doesn't meet our posting requirements. Please make sure you have a descriptive title and good body.",
            color=discord.Color.red(),
        )

        # Check if the thread title is disallowed
        if any(
            pattern.search(thread.name) for pattern in self.disallowed_title_patterns
        ):
            await thread.send(embed=embed)
            await thread.edit(
                name=f"[REJECTED] {thread.name}"[:100],
                archived=True,
                locked=True,
            )
            return

        # Check if the thread body is disallowed
        messages = [message async for message in thread.history(limit=5)]
        if messages:
            body = messages[-1].content
            if any(pattern.search(body) for pattern in self.disallowed_body_patterns):
                await thread.send(embed=embed)
                await thread.edit(
                    name=f"[REJECTED] {thread.name}"[:100],
                    archived=True,
                    locked=True,
                )
                return

        # Check if the thread creator has an existing open thread
        for existing_thread in channel.threads:
            if (
                existing_thread.owner_id == thread.owner_id
                and not existing_thread.archived
                and existing_thread.id != thread.id
            ):
                embed = discord.Embed(
                    title="Duplicate Thread Detected",
                    description="You already have an open thread. Please continue in your existing thread.",
                    color=discord.Color.orange(),
                )
                await thread.send(embed=embed)
                await thread.edit(
                    name=f"[DUPLICATE] {thread.name}"[:100],
                    archived=True,
                    locked=True,
                )
                return

        embed = discord.Embed(
            title="Welcome!",
            description="Your thread has been created successfully!",
            color=discord.Color.blue(),
        )
        await thread.send(embed=embed)