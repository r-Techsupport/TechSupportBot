"""
Module for defining the grabs extension
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import configuration
import ui
from core import auxiliary, cogs, cryptography
from database.schema import Grab

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Grab plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

    await bot.add_cog(Grabber(bot=bot))


async def invalid_channel(interaction: discord.Interaction) -> bool:
    """A method to check channels against the whitelist
    If the channel is not in the whitelist, the command execution is halted
    This is expected to be used in a @app_commands.check call

    Args:
        interaction (discord.Interaction): The interaction that called this command

    Raises:
        CheckFailure: Raised if grabs aren't allowed in the given channel

    Returns:
        bool: If the grabs are allowed in the channel the command was run in
    """
    allowed_channels = configuration.get_config_entry(
        interaction.guild.id, "grab_allowed_channels"
    )
    # Check if list is empty. If it is, allow all channels
    if not allowed_channels:
        return True
    # If this list is not empty, it is a strict whitelist
    if str(interaction.channel.id) in allowed_channels:
        return True
    raise app_commands.CheckFailure("Grabs are disabled for this channel")


async def get_visible_grabs(
    user: discord.Member, interaction: discord.Interaction
) -> list[Grab]:
    """Fetch a user's grabs in this server, respecting the channel's NSFW setting.

    Args:
        user (discord.Member): The user to get grabs for
        interaction (discord.Interaction): The interaction providing the guild and channel

    Returns:
        list[Grab]: The user's grabs in this guild, filtered by the channel's NSFW setting
    """
    nsfw_filter = () if interaction.channel.is_nsfw() else (Grab.nsfw.eq(False),)

    return await Grab.objects().where(
        Grab.author_id == str(user.id),
        Grab.guild == str(interaction.guild.id),
        *nsfw_filter,
    )


class Grabber(cogs.BaseCog):
    """Class for the actual commands

    Attributes:
        SEARCH_LIMIT (int): The max amount of messages to search when grabbing
        grab_group (app_commands.Group): The group for the /grab commands
    """

    SEARCH_LIMIT: int = 20
    grab_group: app_commands.Group = app_commands.Group(
        name="grab", description="Save and retrieve grabbed messages", guild_only=True
    )

    @app_commands.guild_only()
    @app_commands.check(invalid_channel)
    @grab_group.command(
        name="message",
        description="Saves a recent message from a user",
    )
    async def grab_user(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Save a recent message using /grab message.
        This will only search for 20 messages

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The user to search for grabs from
        """

        if user.bot:
            embed = auxiliary.prepare_deny_embed(
                message="Ain't gonna catch me slipping!"
            )
            await interaction.response.send_message(embed=embed)
            return

        if user == interaction.user:
            embed = auxiliary.prepare_deny_embed(
                message="You can't do this to yourself"
            )
            await interaction.response.send_message(embed=embed)
            return

        grab_message = None

        async for message in interaction.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user:
                grab_message = message.content
                break

        if not grab_message:
            embed = auxiliary.prepare_deny_embed(
                message=f"Could not find a recent message from user {user}"
            )
            await interaction.response.send_message(embed=embed)
            return

        grab_hash = cryptography.hash_text(grab_message)

        grab = (
            await Grab.objects()
            .where(
                Grab.author_id == str(user.id),
                Grab.message_hash == grab_hash,
            )
            .first()
        )

        if grab:
            embed = auxiliary.prepare_deny_embed(message="That grab already exists!")
            await interaction.response.send_message(embed=embed)
            return

        grab = Grab(
            author_id=str(user.id),
            channel=str(interaction.channel.id),
            guild=str(interaction.guild.id),
            message=cryptography.encrypt(grab_message),
            message_hash=grab_hash,
            nsfw=interaction.channel.is_nsfw(),
        )
        await grab.save()

        embed = auxiliary.prepare_confirm_embed(
            message=f"Successfully saved: '*{grab_message}*'"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.check(invalid_channel)
    @grab_group.command(
        name="all",
        description="Returns all grabbed messages for a user",
    )
    async def all_grabs(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Discord command to get a paginated list of all grabs from a given user

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The user to get all the grabs from
        """
        is_nsfw = interaction.channel.is_nsfw()
        if user.bot:
            embed = auxiliary.prepare_deny_embed(
                message="Ain't gonna catch me slipping!"
            )
            await interaction.response.send_message(embed=embed)
            return

        grabs = await get_visible_grabs(user, interaction)

        if not grabs:
            embed = auxiliary.prepare_deny_embed(
                message=f"No grabs found for {user.name}"
            )
            await interaction.response.send_message(embed=embed)
            return

        grabs.sort(reverse=True, key=lambda grab: grab.time)

        embeds = []
        field_counter = 1
        for index, grab_ in enumerate(grabs):
            description = "Let's take a stroll down memory lane..."
            if not is_nsfw:
                description = "Note: *NSFW grabs are hidden in this channel*"
            embed = (
                discord.Embed(
                    title=f"Grabs for {user.name}",
                    description=description,
                )
                if field_counter == 1
                else embed
            )
            embed.add_field(
                name=f'"{cryptography.decrypt(grab_.message)}"',
                value=grab_.time.date(),
                inline=False,
            )
            if (
                field_counter
                == configuration.get_config_entry(interaction.guild.id, "grab_per_page")
                or index == len(list(grabs)) - 1
            ):
                embed.set_thumbnail(url=user.display_avatar.url)
                embed.color = discord.Color.orange()
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        await interaction.response.defer()
        await ui.PaginateView().send(
            channel=interaction.channel,
            author=interaction.user,
            data=embeds,
            interaction=interaction,
        )

    @app_commands.guild_only()
    @app_commands.check(invalid_channel)
    @grab_group.command(
        name="random",
        description="Returns a random grabbed message for a user "
        + "(note: NSFW messages are filtered by channel settings)",
    )
    async def random_grab(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Discord command to get a random grab from the given user

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The user to get a random grab from
        """

        if user.bot:
            embed = auxiliary.prepare_deny_embed(
                message="Ain't gonna catch me slipping!"
            )
            await interaction.response.send_message(embed=embed)
            return

        grabs = await get_visible_grabs(user, interaction)

        if not grabs:
            embed = auxiliary.prepare_deny_embed(message=f"No grabs found for {user}")
            await interaction.response.send_message(embed=embed)
            return

        random_index = random.randint(0, len(grabs) - 1)
        grab = grabs[random_index]

        embed = discord.Embed(
            title=f'"{cryptography.decrypt(grab.message)}"',
            description=f"{user.name}, {grab.time.date()}",
        )

        embed.color = discord.Color.orange()

        embed.set_thumbnail(url=user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.check(invalid_channel)
    @grab_group.command(
        name="delete",
        description="Deleted a specific grab from a user by the message",
    )
    async def delete_grab(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        *,
        message: str,
    ) -> None:
        """Deletes a given grab by exact string

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The user to delete a grab from
            message (str): The exact string of the grab to delete
        """
        # Stop execution if the invoker isn't the target or an admin
        if (
            not interaction.user.id == user.id
            and not interaction.user.guild_permissions.administrator
        ):
            embed = auxiliary.prepare_deny_embed(
                message="You don't have sufficient permissions to do this!"
            )
            await interaction.response.send_message(embed=embed)
            return

        grab_hash = cryptography.hash_text(message)
        grab = (
            await Grab.objects()
            .where(
                Grab.author_id == str(user.id),
                Grab.guild == str(interaction.guild.id),
                Grab.message_hash == grab_hash,
            )
            .first()
        )

        if not grab:
            embed = auxiliary.prepare_deny_embed(
                message=f"Grab `{message}` not found for {user}"
            )
            await interaction.response.send_message(embed=embed)
            return
        await grab.remove()

        embed = auxiliary.prepare_confirm_embed(message="Grab succesfully deleted!")
        await interaction.response.send_message(embed=embed)
