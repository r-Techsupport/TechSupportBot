"""The support forum management features"""

from __future__ import annotations

import asyncio
import datetime
import random
import re
from typing import TYPE_CHECKING, Self

import discord
import munch
import ui
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
        key="close_message",
        datatype="str",
        title="The message displayed on closed threads",
        description="The message displayed on closed threads",
        default="thread closed",
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
    config.add(
        key="welcome_message",
        datatype="str",
        title="The message displayed on new threads",
        description="The message displayed on new threads",
        default="thread welcome",
    )
    await bot.add_cog(ForumChannel(bot=bot, extension_name="forum"))
    bot.add_extension_config("forum", config)


STATUS_CONFIG = {
    "solved": {
        "title": "Thread marked as solved",
        "prefix": "[SOLVED]",
        "color": discord.Color.green(),
        "message_key": "solve_message",
    },
    "closed": {
        "title": "Thread marked as closed",
        "prefix": "[CLOSED]",
        "color": discord.Color.red(),
        "message_key": "close_message",
    },
    "rejected": {
        "title": "Thread rejected",
        "prefix": "[REJECTED]",
        "color": discord.Color.red(),
        "message_key": "reject_message",
    },
    "duplicate": {
        "title": "Duplicate thread detected",
        "prefix": "[DUPLICATE]",
        "color": discord.Color.orange(),
        "message_key": "duplicate_message",
    },
    "abandoned": {
        "title": "Abandoned thread archived",
        "prefix": "[ABANDONED]",
        "color": discord.Color.blurple(),
        "message_key": "abandoned_message",
    },
}


class ForumChannel(cogs.LoopCog):
    """The cog that holds the forum channel commands and helper functions

    Attributes:
        forum_group (app_commands.Group): The group for the /forum commands
    """

    forum_group: app_commands.Group = app_commands.Group(
        name="forum", description="...", extras={"module": "forum"}
    )

    @forum_group.command(
        name="mark",
        description="Mark a support forum thread",
        extras={"module": "forum"},
    )
    async def mark_thread_command(
        self: Self,
        interaction: discord.Interaction,
        status: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        config = self.bot.guild_configs[str(interaction.guild.id)]
        forum_channel = await interaction.guild.fetch_channel(
            int(config.extensions.forum.forum_channel_id.value)
        )

        invalid_embed = discord.Embed(
            title="Invalid location",
            description="The location this was run isn't a valid support forum",
            color=discord.Color.red(),
        )

        # Check 1: Ensure command was run in the forum channel
        if (
            not hasattr(interaction.channel, "parent")
            or interaction.channel.parent != forum_channel
        ):
            await interaction.followup.send(embed=invalid_embed, ephemeral=True)
            return

        is_staff = is_thread_staff(interaction.user, interaction.guild, config)
        is_owner = interaction.user == interaction.channel.owner

        # Check 2: Ensure status is valid
        if status not in ("solved", "closed", "rejected", "abandoned"):
            embed = discord.Embed(
                title="Invalid status",
                description="That status is not valid",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if status in ("rejected", "abandoned") and not is_staff:
            denied = True
        elif status in ("solved", "closed") and not (is_staff or is_owner):
            denied = True
        else:
            denied = False

        # Check 3: Ensure permissions are valid
        if denied:
            embed = discord.Embed(
                title="Permission denied",
                description="You cannot do this",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        confirm_embed = auxiliary.prepare_confirm_embed(f"Thread marked as {status}!")
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

        await mark_thread(interaction.channel, config, status)

    @mark_thread_command.autocomplete("status")
    async def status_autocomplete(
        self: Self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """This is the autocomplete function for status on the thread mark command
        This parses a list of valid statuses and shows the user the list they can actually use

        Args:
            self (Self): _description_
            interaction (discord.Interaction): The interaction that is calling the command
            current (str): The current choice the user is typing

        Returns:
            list[app_commands.Choice[str]]: The list of all valid choices
                that fit with the users current selection
        """

        config = self.bot.guild_configs[str(interaction.guild.id)]

        is_staff = is_thread_staff(interaction.user, interaction.guild, config)
        is_owner = (
            hasattr(interaction.channel, "owner")
            and interaction.user == interaction.channel.owner
        )

        choices = []

        # Staff can do all 4 options
        if is_staff:
            choices.extend(
                [
                    app_commands.Choice(name="Rejected", value="rejected"),
                    app_commands.Choice(name="Abandoned", value="abandoned"),
                    app_commands.Choice(name="Closed", value="closed"),
                    app_commands.Choice(name="Solved", value="solved"),
                ]
            )

        # The OP can mark their thread closed or solved, but not rejected or abandoned
        elif is_owner:
            choices.extend(
                [
                    app_commands.Choice(name="Closed", value="closed"),
                    app_commands.Choice(name="Solved", value="solved"),
                ]
            )

        # This just filters out anything not matching what the user is typing
        return [choice for choice in choices if current.lower() in choice.name.lower()]

    @forum_group.command(
        name="unsolved",
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
        mention_threads: list[discord.Thread] = channel.threads
        if len(mention_threads) == 0:
            embed = discord.Embed(
                title="Unsolved",
                description="No unsolved issues. Hopefully not a bug",
                color=discord.Color.blurple(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        # To prevent bias, we randomize the open threads
        random.shuffle(mention_threads)
        embeds = []
        index = 1
        running_desc = ""
        embed = discord.Embed(title="Unsolved", color=discord.Color.blurple())
        for thread in mention_threads:
            if index % 10 == 0:
                embed.description = running_desc
                embeds.append(embed)
                embed = discord.Embed(title="Unsolved", color=discord.Color.blurple())
                running_desc = ""
            running_desc += f"{thread.name}: {thread.mention}\n"
            index += 1

        embed.description = running_desc
        embeds.append(embed)

        view = ui.PaginateView()
        await view.send(
            interaction.channel, interaction.user, embeds, interaction, True
        )

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
            await mark_thread(thread, config, "rejected")
            return

        # Check if the thread body is disallowed
        messages = [message async for message in thread.history(limit=5)]
        if messages:
            body = messages[-1].content
            disallowed_body_patterns = create_regex_list(
                config.extensions.forum.body_regex_list.value
            )
            if any(pattern.search(body) for pattern in disallowed_body_patterns):
                await mark_thread(thread, config, "rejected")
                return
            if body.lower() == thread.name.lower() or len(body.lower()) < len(
                thread.name.lower()
            ):
                await mark_thread(thread, config, "rejected")
                return

        # Check if the thread creator has an existing open thread
        for existing_thread in channel.threads:
            if (
                existing_thread.owner_id == thread.owner_id
                and not existing_thread.archived
                and existing_thread.id != thread.id
            ):
                await mark_thread(thread, config, "duplicate")
                return

        embed = discord.Embed(
            title="Welcome!",
            description=config.extensions.forum.welcome_message.value,
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
                    await mark_thread(existing_thread, config, "abandoned")

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


async def mark_thread(
    thread: discord.Thread,
    config: munch.Munch,
    status: str,
) -> None:
    """This modifies a thread, can be marked as any of the options in STATUS_CONFIG
    No validation is done, assuming data passed here is always valid

    Args:
        thread (discord.Thread): The thread to modify
        config (munch.Munch): The guild config
        status (str): The status to modify the thread with
    """
    data = STATUS_CONFIG[status]

    embed = discord.Embed(
        title=data["title"],
        description=getattr(config.extensions.forum, data["message_key"]).value,
        color=data["color"],
    )

    await thread.send(content=thread.owner.mention, embed=embed)

    await thread.edit(
        name=f"{data['prefix']} {thread.name}"[:100],
        archived=True,
        locked=True,
    )
