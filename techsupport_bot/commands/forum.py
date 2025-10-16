"""The support forum management features"""

from __future__ import annotations

import asyncio
import datetime
import random
import re
from typing import TYPE_CHECKING, Self

import discord
import munch
from core import auxiliary, cogs, extensionconfig
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
    config.add(
        key="staff_role_ids",
        datatype="list[int]",
        title="List of role ids as ints for staff, able to mark threads solved/abandoned/rejected",
        description="List of role ids as ints for staff, able to mark threads solved/abandoned/rejected",
        default=[],
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
        await interaction.response.defer(ephemeral=True)
        config = self.bot.guild_configs[str(interaction.guild.id)]
        channel = await interaction.guild.fetch_channel(
            int(config.extensions.forum.forum_channel_id.value)
        )

        invalid_embed = discord.Embed(
            title="Invalid location",
            description="The location this was run isn't a valid support forum",
            color=discord.Color.red(),
        )

        if not hasattr(interaction.channel, "parent"):
            await interaction.followup.send(embed=invalid_embed, ephemeral=True)
            return
        if not interaction.channel.parent == channel:
            await interaction.followup.send(embed=invalid_embed, ephemeral=True)
            return

        if not (
            interaction.user == interaction.channel.owner
            or is_thread_staff(interaction.user, interaction.guild, config)
        ):
            embed = discord.Embed(
                title="Permission denied",
                description="You cannot do this",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = auxiliary.prepare_confirm_embed("Thread marked as solved!")
        await interaction.followup.send(embed=embed, ephemeral=True)
        await mark_thread_solved(interaction.channel, config)

    @forum_group.command(
        name="reject",
        description="Mark a support forum thread as rejected",
        extras={"module": "forum"},
    )
    async def markRejected(self: Self, interaction: discord.Interaction) -> None:
        """A command to mark the thread as rejected
        Usable by staff

        Args:
            interaction (discord.Interaction): The interaction that called the command
        """
        await interaction.response.defer(ephemeral=True)
        config = self.bot.guild_configs[str(interaction.guild.id)]
        channel = await interaction.guild.fetch_channel(
            int(config.extensions.forum.forum_channel_id.value)
        )

        invalid_embed = discord.Embed(
            title="Invalid location",
            description="The location this was run isn't a valid support forum",
            color=discord.Color.red(),
        )

        if not hasattr(interaction.channel, "parent"):
            await interaction.followup.send(embed=invalid_embed, ephemeral=True)
            return
        if not interaction.channel.parent == channel:
            await interaction.followup.send(embed=invalid_embed, ephemeral=True)
            return

        if not (is_thread_staff(interaction.user, interaction.guild, config)):
            embed = discord.Embed(
                title="Permission denied",
                description="You cannot do this",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = auxiliary.prepare_confirm_embed("Thread marked as rejected!")
        await interaction.followup.send(embed=embed, ephemeral=True)
        await mark_thread_rejected(interaction.channel, config)

    @forum_group.command(
        name="abandon",
        description="Mark a support forum thread as abandoned",
        extras={"module": "forum"},
    )
    async def markAbandoned(self: Self, interaction: discord.Interaction) -> None:
        """A command to mark the thread as abandoned
        Usable by staff

        Args:
            interaction (discord.Interaction): The interaction that called the command
        """
        await interaction.response.defer(ephemeral=True)
        config = self.bot.guild_configs[str(interaction.guild.id)]
        channel = await interaction.guild.fetch_channel(
            int(config.extensions.forum.forum_channel_id.value)
        )

        invalid_embed = discord.Embed(
            title="Invalid location",
            description="The location this was run isn't a valid support forum",
            color=discord.Color.red(),
        )

        if not hasattr(interaction.channel, "parent"):
            await interaction.followup.send(embed=invalid_embed, ephemeral=True)
            return
        if not interaction.channel.parent == channel:
            await interaction.followup.send(embed=invalid_embed, ephemeral=True)
            return

        if not (is_thread_staff(interaction.user, interaction.guild, config)):
            embed = discord.Embed(
                title="Permission denied",
                description="You cannot do this",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed = auxiliary.prepare_confirm_embed("Thread marked as abandoned!")
        await interaction.followup.send(embed=embed, ephemeral=True)
        await mark_thread_abandoned(interaction.channel, config)

    @forum_group.command(
        name="get-unsolved",
        description="Gets a collection of unsolved issues",
        extras={"module": "forum"},
    )
    async def showUnsolved(self: Self, interaction: discord.Interaction) -> None:
        """A command to mark the thread as abandoned
        Usable by all

        Args:
            interaction (discord.Interaction): The interaction that called the command
        """
        await interaction.response.defer(ephemeral=True)
        config = self.bot.guild_configs[str(interaction.guild.id)]
        channel = await interaction.guild.fetch_channel(
            int(config.extensions.forum.forum_channel_id.value)
        )
        mention_threads = "\n".join(
            [
                thread.mention
                for thread in random.sample(
                    channel.threads, min(len(channel.threads), 5)
                )
            ]
        )
        embed = discord.Embed(title="Unsolved", description=mention_threads)
        await interaction.followup.send(embed=embed, ephemeral=True)

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

        # Check if the thread title is disallowed
        if any(pattern.search(thread.name) for pattern in disallowed_title_patterns):
            await mark_thread_rejected(thread, config)
            return

        # Check if the thread body is disallowed
        messages = [message async for message in thread.history(limit=5)]
        if messages:
            body = messages[-1].content
            disallowed_body_patterns = create_regex_list(
                config.extensions.forum.body_regex_list.value
            )
            if any(pattern.search(body) for pattern in disallowed_body_patterns):
                await mark_thread_rejected(thread, config)
                return
            if body.lower() == thread.name.lower() or len(body.lower()) < len(
                thread.name.lower()
            ):
                await mark_thread_rejected(thread, config)
                return

        # Check if the thread creator has an existing open thread
        for existing_thread in channel.threads:
            if (
                existing_thread.owner_id == thread.owner_id
                and not existing_thread.archived
                and existing_thread.id != thread.id
            ):
                await mark_thread_duplicated(thread, config)
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
                    await mark_thread_abandoned(existing_thread, config)

    async def wait(self: Self, config: munch.Munch, _: discord.Guild) -> None:
        """This waits and rechecks every 5 minutes to search for old threads

        Args:
            config (munch.Munch): The guild config where the loop is taking place
        """
        await asyncio.sleep(300)


def create_regex_list(str_list: list[str]) -> list[re.Pattern[str]]:
    """This turns a list of strings into a list of complied regex

    Args:
        str_list (list[str]): The list of string versions of regexs

    Returns:
        list[re.Pattern[str]]: The compiled list of regex for later use
    """
    return [re.compile(p, re.IGNORECASE) for p in str_list]


def is_thread_staff(
    user: discord.User, guild: discord.Guild, config: munch.Munch
) -> bool:
    if staff_roles := config.extensions.forum.staff_role_ids.value:
        roles = (discord.utils.get(guild.roles, id=int(role)) for role in staff_roles)
        status = any((role in user.roles for role in roles))
        if status:
            return True
    return False


async def mark_thread_solved(thread: discord.Thread, config: munch.Munch) -> None:
    solved_embed = discord.Embed(
        title="Thread marked as solved",
        description=config.extensions.forum.solve_message.value,
        color=discord.Color.green(),
    )

    await thread.send(content=thread.owner.mention, embed=solved_embed)
    await thread.edit(
        name=f"[SOLVED] {thread.name}"[:100],
        archived=True,
        locked=True,
    )


async def mark_thread_rejected(thread: discord.Thread, config: munch.Munch) -> None:
    reject_embed = discord.Embed(
        title="Thread rejected",
        description=config.extensions.forum.reject_message.value,
        color=discord.Color.red(),
    )

    await thread.send(content=thread.owner.mention, embed=reject_embed)
    await thread.edit(
        name=f"[REJECTED] {thread.name}"[:100],
        archived=True,
        locked=True,
    )


async def mark_thread_duplicated(thread: discord.Thread, config: munch.Munch) -> None:
    duplicate_embed = discord.Embed(
        title="Duplicate thread detected",
        description=config.extensions.forum.duplicate_message.value,
        color=discord.Color.orange(),
    )

    await thread.send(content=thread.owner.mention, embed=duplicate_embed)
    await thread.edit(
        name=f"[DUPLICATE] {thread.name}"[:100],
        archived=True,
        locked=True,
    )


async def mark_thread_abandoned(thread: discord.Thread, config: munch.Munch) -> None:
    abandoned_embed = discord.Embed(
        title="Abandoned thread archived",
        description=config.extensions.forum.abandoned_message.value,
        color=discord.Color.blurple(),
    )

    await thread.send(content=thread.owner.mention, embed=abandoned_embed)
    await thread.edit(
        name=f"[ABANDONED] {thread.name}"[:100],
        archived=True,
        locked=True,
    )
