"""Module for the who extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import ui
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, extensionconfig, moderation
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Who plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

    config = extensionconfig.ExtensionConfig()
    config.add(
        key="note_role",
        datatype="str",
        title="Note role",
        description="The name of the role to be added when a note is added to a user",
        default=None,
    )
    config.add(
        key="note_bypass",
        datatype="list",
        title="Note bypass list",
        description=(
            "A list of roles that shouldn't have notes set or the note role assigned"
        ),
        default=["Moderator"],
    )
    config.add(
        key="note_readers",
        datatype="list",
        title="Note Reader Roles",
        description="Users with roles in this list will be able to use whois",
        default=[],
    )
    config.add(
        key="note_writers",
        datatype="list",
        title="Note Writer Roles",
        description="Users with roles in this list will be able to create or delete notes",
        default=[],
    )

    await bot.add_cog(Notes(bot=bot, extension_name="notes"))
    bot.add_extension_config("notes", config)


async def is_reader(interaction: discord.Interaction) -> bool:
    """Checks whether invoker can read notes. If at least one reader
    role is not set, NO members can read notes

    Args:
        interaction (discord.Interaction): The interaction in which the whois command occured

    Raises:
        MissingAnyRole: Raised if the user is lacking any reader role,
            but there are roles defined
        AppCommandError: Raised if there are no note_readers set in the config

    Returns:
        bool: True if the user can run, False if they cannot
    """

    config = interaction.client.guild_configs[str(interaction.guild.id)]
    if reader_roles := config.extensions.notes.note_readers.value:
        roles = (
            discord.utils.get(interaction.guild.roles, name=role)
            for role in reader_roles
        )
        status = any((role in interaction.user.roles for role in roles))
        if not status:
            raise app_commands.MissingAnyRole(reader_roles)
        return True

    # Reader_roles are empty (not set)
    message = "There aren't any `note_readers` roles set in the config!"

    raise app_commands.AppCommandError(message)


async def is_writer(interaction: discord.Interaction) -> bool:
    """Checks whether invoker can write notes. If at least one writer
    role is not set, NO members can write notes

    Args:
        interaction (discord.Interaction): The interaction in which the whois command occured

    Raises:
        MissingAnyRole: Raised if the user is lacking any writer role,
            but there are roles defined
        AppCommandError: Raised if there are no note_writers set in the config

    Returns:
        bool: True if the user can run, False if they cannot
    """
    config = interaction.client.guild_configs[str(interaction.guild.id)]
    if writer_roles := config.extensions.notes.note_writers.value:
        roles = (
            discord.utils.get(interaction.guild.roles, name=role)
            for role in writer_roles
        )
        status = any((role in interaction.user.roles for role in roles))
        if not status:
            raise app_commands.MissingAnyRole(writer_roles)
        return True

    # Reader_roles are empty (not set)
    message = "There aren't any `note_writers` roles set in the config!"

    raise app_commands.AppCommandError(message)


class Notes(cogs.BaseCog):
    """Class to set up who for the extension.

    Attributes:
        notes (app_commands.Group): The group for the /note commands

    """

    notes: app_commands.Group = app_commands.Group(
        name="notes", description="Command Group for the Notes Extension"
    )

    @app_commands.check(is_reader)
    @app_commands.check(is_writer)
    @notes.command(
        name="set",
        description="Adds a note to a given user.",
        extras={
            "brief": "Sets a note for a user",
            "usage": "@user [note]",
            "module": "notes",
        },
    )
    async def set_note(
        self: Self, interaction: discord.Interaction, user: discord.Member, body: str
    ) -> None:
        """Adds a new note to a user
        This is the entrance for the /note set command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The member to add the note to
            body (str): The contents of the note being created
        """
        if interaction.user.id == user.id:
            embed = auxiliary.prepare_deny_embed(
                message="You cannot add a note for yourself"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        note = self.bot.models.UserNote(
            user_id=str(user.id),
            guild_id=str(interaction.guild.id),
            author_id=str(interaction.user.id),
            body=body,
        )

        config = self.bot.guild_configs[str(interaction.guild.id)]

        # Check to make sure notes are allowed to be assigned
        for name in config.extensions.notes.note_bypass.value:
            role_check = discord.utils.get(interaction.guild.roles, name=name)
            if not role_check:
                continue
            if role_check in getattr(user, "roles", []):
                embed = auxiliary.prepare_deny_embed(
                    message=f"You cannot assign notes to `{user}` because "
                    + f"they have `{role_check}` role",
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        await note.create()

        role = discord.utils.get(
            interaction.guild.roles, name=config.extensions.notes.note_role.value
        )

        if not role:
            embed = auxiliary.prepare_confirm_embed(
                message=f"Note created for `{user}`, but no note "
                + "role is configured so no role was added",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await user.add_roles(role, reason=f"First note was added by {interaction.user}")

        embed = auxiliary.prepare_confirm_embed(message=f"Note created for `{user}`")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.check(is_reader)
    @app_commands.check(is_writer)
    @notes.command(
        name="clear",
        description="Clears all existing notes for a user",
        extras={
            "brief": "Clears all notes for a user",
            "usage": "@user",
            "module": "notes",
        },
    )
    async def clear_notes(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Clears all notes on a given user
        This is the entrace for the /note clear command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The member to remove all notes from
        """
        notes = await moderation.get_all_notes(self.bot, user, interaction.guild)

        if not notes:
            embed = auxiliary.prepare_deny_embed(
                message="There are no notes for that user"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        view = ui.Confirm()

        await view.send(
            message=f"Are you sure you want to clear {len(notes)} notes?",
            channel=interaction.channel,
            author=interaction.user,
            interaction=interaction,
            ephemeral=True,
        )

        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            embed = auxiliary.prepare_deny_embed(
                message=f"Notes for `{user}` were not cleared"
            )
            await view.followup.send(embed=embed, ephemeral=True)
            return

        for note in notes:
            await note.delete()

        config = self.bot.guild_configs[str(interaction.guild.id)]
        role = discord.utils.get(
            interaction.guild.roles, name=config.extensions.notes.note_role.value
        )
        if role:
            await user.remove_roles(
                role, reason=f"Notes were cleared by {interaction.user}"
            )

        embed = auxiliary.prepare_confirm_embed(message=f"Notes cleared for `{user}`")
        await view.followup.send(embed=embed, ephemeral=True)

    @app_commands.check(is_reader)
    @notes.command(
        name="all",
        description="Gets all notes for a user instead of just new ones",
        extras={
            "brief": "Gets all notes for a user",
            "usage": "@user",
            "module": "notes",
        },
    )
    async def all_notes(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Gets a file containing every note on a user
        This is the entrance for the /note all command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            member (discord.Member): The member to get all notes for
        """
        notes = await moderation.get_all_notes(self.bot, member, interaction.guild)

        embeds = build_note_embeds(interaction.guild, member, notes)

        await interaction.response.defer(ephemeral=True)
        view = ui.PaginateView()
        await view.send(
            interaction.channel, interaction.user, embeds, interaction, True
        )

    # re-adds note role back to joining users
    @commands.Cog.listener()
    async def on_member_join(self: Self, member: discord.Member) -> None:
        """Automatic listener to look at users when they join the guild.
        This is to apply the note role back to joining users

        Args:
            member (discord.Member): The member who has just joined
        """
        config = self.bot.guild_configs[str(member.guild.id)]
        if not self.extension_enabled(config):
            return

        role = discord.utils.get(
            member.guild.roles, name=config.extensions.notes.note_role.value
        )
        if not role:
            return

        user_notes = await moderation.get_all_notes(self.bot, member, member.guild)
        if not user_notes:
            return

        await member.add_roles(role, reason="Noted user has joined the guild")

        log_channel = config.get("logging_channel")
        await self.bot.logger.send_log(
            message=f"Found noted user with ID {member.id} joining - re-adding role",
            level=LogLevel.INFO,
            context=LogContext(guild=member.guild),
            channel=log_channel,
        )


def build_note_embeds(
    guild: discord.Guild,
    member: discord.Member,
    notes: list[bot.models.UserNote],
) -> list[discord.Embed]:
    """Makes a list of embeds with 6 notes per page, for a given user

    Args:
        guild (discord.Guild): The guild where the notes occured
        member (discord.Member): The member whose notes are being looked for
        notes (list[bot.models.UserNote]): The list of notes from the database

    Returns:
        list[discord.Embed]: The list of well formatted embeds
    """
    embed = auxiliary.generate_basic_embed(
        f"Notes for `{member.display_name}` (`{member.name}`)",
        color=discord.Color.dark_blue(),
    )
    embed.set_footer(text=f"{len(notes)} total notes.")

    embeds = []

    if not notes:
        embed.description = "No notes"
        return [embed]

    for index, note in enumerate(notes):
        if index % 6 == 0 and index > 0:
            embeds.append(embed)
            embed = auxiliary.generate_basic_embed(
                f"Notes for `{member.display_name}` (`{member.name}`)",
                color=discord.Color.dark_blue(),
            )
            embed.set_footer(text=f"{len(notes)} total notes.")
        author = guild.get_member(int(note.author_id)) or note.author_id
        embed.add_field(
            name=f"Note by {author}",
            value=f"{note.body}\nNote added <t:{int(note.updated.timestamp())}:R>",
        )
    embeds.append(embed)
    return embeds
