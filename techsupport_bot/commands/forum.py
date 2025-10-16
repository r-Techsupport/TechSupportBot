""" ""The channel slowmode modification extension
Holds only a single slash command"""

from __future__ import annotations

import asyncio
import datetime
import re
from typing import TYPE_CHECKING, Self

import discord
import munch
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


class ForumChannel(cogs.LoopCog):
    """The cog that holds the slowmode commands and helper functions"""

    # Hard code default embed types
    reject_embed = discord.Embed(
        title="Thread rejected",
        description="Your thread doesn't meet our posting requirements. Please make sure you have a descriptive title and good body.",
        color=discord.Color.red(),
    )

    duplicate_embed = discord.Embed(
        title="Duplicate thread detected",
        description="You already have an open thread. Please continue in your existing thread.",
        color=discord.Color.orange(),
    )

    abandoned_embed = discord.Embed(
        title="Abandoned thread archived",
        description="It appears this thread has been abandoned. You are welcome to create another thread",
        color=discord.Color.blurple(),
    )

    solved_embed = discord.Embed(
        title="Thread marked as solved",
        description="This thread has been archived and locked.",
        color=discord.Color.green(),
    )

    forum_group: app_commands.Group = app_commands.Group(
        name="forum", description="...", extras={"module": "forum"}
    )

    channel_id = "1288279278839926855"
    max_age_minutes = 1
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
        description="Mark a support forum thread as solved",
        extras={"module": "forum"},
    )
    async def markSolved(self: Self, interaction: discord.Interaction) -> None:
        channel = await interaction.guild.fetch_channel(int(self.channel_id))
        if (
            hasattr(interaction.channel, "parent")
            and interaction.channel.parent == channel
        ):
            if interaction.user != interaction.channel.owner:
                embed = discord.Embed(
                    title="Permission denied",
                    description="You cannot do this",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            await interaction.response.send_message(embed=self.solved_embed)
            await interaction.channel.edit(
                name=f"[SOLVED] {interaction.channel.name}"[:100],
                archived=True,
                locked=True,
            )
        else:
            embed = discord.Embed(
                title="Invalid location",
                description="The location this was run isn't a valid support forum",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_thread_create(self: Self, thread: discord.Thread) -> None:
        channel = await thread.guild.fetch_channel(int(self.channel_id))
        if thread.parent != channel:
            return

        # Check if the thread title is disallowed
        if any(
            pattern.search(thread.name) for pattern in self.disallowed_title_patterns
        ):
            await thread.send(embed=self.reject_embed)
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
                await thread.send(embed=self.reject_embed)
                await thread.edit(
                    name=f"[REJECTED] {thread.name}"[:100],
                    archived=True,
                    locked=True,
                )
                return
            if body.lower() == thread.name.lower() or len(body.lower()) < len(
                thread.name.lower()
            ):
                await thread.send(embed=self.reject_embed)
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
                await thread.send(embed=self.duplicate_embed)
                await thread.edit(
                    name=f"[DUPLICATE] {thread.name}"[:100],
                    archived=True,
                    locked=True,
                )
                return

        embed = discord.Embed(
            title="Welcome!",
            description=(
                "Your thread has been created successfully!\n"
                "Run the command </forum solved:1428385659311095920> when your issue gets solved"
            ),
            color=discord.Color.blue(),
        )
        await thread.send(embed=embed)

    async def execute(self: Self, config: munch.Munch, guild: discord.Guild) -> None:
        """The main entry point for the loop for kanye
        This is executed automatically and shouldn't be called manually

        Args:
            config (munch.Munch): The guild config where the loop is taking place
            guild (discord.Guild): The guild where the loop is taking place
        """
        channel = await guild.fetch_channel(int(self.channel_id))
        for existing_thread in channel.threads:
            if not existing_thread.archived and not existing_thread.locked:
                most_recent_message_id = existing_thread.last_message_id
                most_recent_message = await existing_thread.fetch_message(
                    most_recent_message_id
                )
                if datetime.datetime.now(
                    datetime.timezone.utc
                ) - most_recent_message.created_at > datetime.timedelta(
                    minutes=self.max_age_minutes
                ):
                    await existing_thread.send(embed=self.abandoned_embed)
                    await existing_thread.edit(
                        name=f"[ABANDONED] {existing_thread.name}"[:100],
                        archived=True,
                        locked=True,
                    )

    async def wait(self: Self, config: munch.Munch, _: discord.Guild) -> None:
        """This sleeps a random amount of time between Kanye quotes

        Args:
            config (munch.Munch): The guild config where the loop is taking place
        """
        await asyncio.sleep(self.max_age_minutes * 60)
