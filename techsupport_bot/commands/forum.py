"""The support forum management features"""

from __future__ import annotations

import asyncio
import datetime
import re
from typing import TYPE_CHECKING, Self

import discord
import munch
from core import cogs, extensionconfig
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the forum channel cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="forum_channel_id",
        datatype="str",
        title="forum channel",
        description="The forum channel id as a string to manage threads in",
        default="",
    )
    config.add(
        key="max_age_minutes",
        datatype="int",
        title="Max age in minutes",
        description="The max age of a thread before it times out",
        default=1440,
    )
    config.add(
        key="title_regex_list",
        datatype="list[str]",
        title="List of regex to ban in titles",
        description="List of regex to ban in titles",
        default=[""],
    )
    config.add(
        key="body_regex_list",
        datatype="list[str]",
        title="List of regex to ban in bodies",
        description="List of regex to ban in bodies",
        default=[""],
    )
    config.add(
        key="reject_message",
        datatype="str",
        title="The message displayed on rejected threads",
        description="The message displayed on rejected threads",
        default="thread rejected",
    )
    config.add(
        key="duplicate_message",
        datatype="str",
        title="The message displayed on duplicated threads",
        description="The message displayed on duplicated threads",
        default="thread duplicated",
    )
    config.add(
        key="solve_message",
        datatype="str",
        title="The message displayed on solved threads",
        description="The message displayed on solved threads",
        default="thread solved",
    )
    config.add(
        key="abandoned_message",
        datatype="str",
        title="The message displayed on abandoned threads",
        description="The message displayed on abandoned threads",
        default="thread abandoned",
    )
    await bot.add_cog(ForumChannel(bot=bot, extension_name="forum"))
    bot.add_extension_config("forum", config)


class ForumChannel(cogs.LoopCog):
    """The cog that holds the forum channel commands and helper functions

    Attributes:
        forum_group (app_commands.Group): The group for the /forum commands
    """

    forum_group: app_commands.Group = app_commands.Group(
        name="forum", description="...", extras={"module": "forum"}
    )

    @forum_group.command(
        name="solved",
        description="Mark a support forum thread as solved",
        extras={"module": "forum"},
    )
    async def markSolved(self: Self, interaction: discord.Interaction) -> None:
        """A command to mark the thread as solved
        Usable by OP and staff

        Args:
            interaction (discord.Interaction): The interaction that called the command
        """
        config = self.bot.guild_configs[str(interaction.guild.id)]
        channel = await interaction.guild.fetch_channel(
            int(config.extensions.forum.forum_channel_id.value)
        )
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
            solved_embed = discord.Embed(
                title="Thread marked as solved",
                description=config.extensions.forum.solve_message.value,
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=solved_embed)
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
        """A listener for threads being created anywhere on the server

        Args:
            thread (discord.Thread): The thread that was created
        """
        config = self.bot.guild_configs[str(thread.guild.id)]
        channel = await thread.guild.fetch_channel(
            int(config.extensions.forum.forum_channel_id.value)
        )
        if thread.parent != channel:
            return

        disallowed_title_patterns = create_regex_list(
            config.extensions.forum.title_regex_list.value
        )

        reject_embed = discord.Embed(
            title="Thread rejected",
            description=config.extensions.forum.reject_message.value,
            color=discord.Color.red(),
        )

        # Check if the thread title is disallowed
        if any(pattern.search(thread.name) for pattern in disallowed_title_patterns):
            await thread.send(embed=reject_embed)
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
            disallowed_body_patterns = create_regex_list(
                config.extensions.forum.body_regex_list.value
            )
            if any(pattern.search(body) for pattern in disallowed_body_patterns):
                await thread.send(embed=reject_embed)
                await thread.edit(
                    name=f"[REJECTED] {thread.name}"[:100],
                    archived=True,
                    locked=True,
                )
                return
            if body.lower() == thread.name.lower() or len(body.lower()) < len(
                thread.name.lower()
            ):
                await thread.send(embed=reject_embed)
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
                duplicate_embed = discord.Embed(
                    title="Duplicate thread detected",
                    description=config.extensions.forum.duplicate_message.value,
                    color=discord.Color.orange(),
                )

                await thread.send(embed=duplicate_embed)
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
        """This is what closes threads after inactivity

        Args:
            config (munch.Munch): The guild config where the loop is taking place
            guild (discord.Guild): The guild where the loop is taking place
        """
        channel = await guild.fetch_channel(
            int(config.extensions.forum.forum_channel_id.value)
        )
        for existing_thread in channel.threads:
            if not existing_thread.archived and not existing_thread.locked:
                most_recent_message_id = existing_thread.last_message_id
                most_recent_message = await existing_thread.fetch_message(
                    most_recent_message_id
                )
                if datetime.datetime.now(
                    datetime.timezone.utc
                ) - most_recent_message.created_at > datetime.timedelta(
                    minutes=config.extensions.forum.max_age_minutes.value
                ):
                    abandoned_embed = discord.Embed(
                        title="Abandoned thread archived",
                        description=config.extensions.forum.abandoned_message.value,
                        color=discord.Color.blurple(),
                    )

                    await existing_thread.send(embed=abandoned_embed)
                    await existing_thread.edit(
                        name=f"[ABANDONED] {existing_thread.name}"[:100],
                        archived=True,
                        locked=True,
                    )

    async def wait(self: Self, config: munch.Munch, _: discord.Guild) -> None:
        """This waits and rechecks every 5 minutes to search for old threads

        Args:
            config (munch.Munch): The guild config where the loop is taking place
        """
        await asyncio.sleep(5)


def create_regex_list(str_list: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in str_list]
