"""
This is a development and issue tracking command designed to dump all attributes
of a given object type.
Current supported is message, member and channel
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import ui
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the debugger cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(Debugger(bot=bot))


class Debugger(cogs.BaseCog):
    """The cog that holds the slowmode commands and helper functions

    Attributes:
        debug_group (app_commands.Group): The group for the /debug commands
    """

    debug_group = app_commands.Group(
        name="debug", description="...", extras={"module": "debug"}
    )

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @debug_group.command(
        name="message",
        description="Searches and displays all the message properties",
        extras={
            "module": "debug",
        },
    )
    async def debug_message(
        self: Self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        id: str,
    ) -> None:
        """Searches for a message by ID in the given channel.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            channel (discord.TextChannel): The channel to find the message in
            id (str): The ID of the message to search for
        """
        await interaction.response.defer(ephemeral=False)
        message = await channel.fetch_message(str(id))
        embeds = build_debug_embed(message)

        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @debug_group.command(
        name="member",
        description="Searches and displays all the member properties",
        extras={
            "module": "debug",
        },
    )
    async def debug_member(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Displays attributes for a member of the guild where the command was run.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            member (discord.Member): The member to search for information on
        """
        await interaction.response.defer(ephemeral=False)
        embeds = build_debug_embed(member)
        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @debug_group.command(
        name="channel",
        description="Searches and displays all the channel properties",
        extras={
            "module": "debug",
        },
    )
    async def debug_channel(
        self: Self, interaction: discord.Interaction, channel: discord.abc.GuildChannel
    ) -> None:
        """Displays attributes for a channel of the guild where the command was run.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            channel (discord.abc.GuildChannel): The channel to search for information on
        """
        await interaction.response.defer(ephemeral=False)
        embeds = build_debug_embed(channel)
        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)


def build_debug_embed(object: object) -> list[discord.Embed]:
    """Builds a list of embeds, with each one at a max of 4000 characters
    This will be every attribute of the given object.

    Args:
        object (object): A discord object that needs to be explored

    Returns:
        list[discord.Embed]: A list of embeds to be displayed in a paginated display
    """
    all_strings = []
    properties_string = ""

    for attribute in dir(object):
        if not attribute.startswith("_"):
            try:
                value = getattr(object, attribute)
            except AttributeError:
                continue

            temp_string = f"**{attribute}:** {value}\n"
            if temp_string.startswith(f"**{attribute}:** <bound method"):
                continue

            all_add_strings = format_attribute_chunks(
                attribute=attribute, value=str(value)
            )
            for print_string in all_add_strings:

                if (len(properties_string) + len(print_string)) > 1500:
                    all_strings.append(properties_string)
                    properties_string = ""

                properties_string += print_string

    all_strings.append(properties_string)

    embeds = []
    for string in all_strings:
        embeds.append(discord.Embed(description=string[:4000]))

    return embeds


def format_attribute_chunks(attribute: str, value: str) -> list[str]:
    """This makes a simple paginated split fields, to break up long attributes

    Args:
        attribute (str): The name of the attribute to be formatted.
        value (str): The string representation of the attribute

    Returns:
        list[str]: A list of attributes, split if needed
    """

    def make_chunk_label(index: int, total: int) -> str:
        return f"**{attribute} ({index}):** " if total > 1 else f"**{attribute}:** "

    max_length = 750

    temp_prefix = f"**{attribute} (999):** "
    chunk_size = max_length - len(temp_prefix) - 1  # Reserve space for prefix and \n

    # Create raw chunks of value
    raw_chunks = [value[i : i + chunk_size] for i in range(0, len(value), chunk_size)]
    total_chunks = len(raw_chunks)

    # Format each chunk with appropriate prefix
    return [
        f"{make_chunk_label(i + 1, total_chunks)}{chunk}\n"
        for i, chunk in enumerate(raw_chunks)
    ]
