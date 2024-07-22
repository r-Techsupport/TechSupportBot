"""Module for the who extension for the discord bot."""

from __future__ import annotations

import datetime
import io
from typing import TYPE_CHECKING, Self

import discord
import ui
import yaml
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, extensionconfig
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

    await bot.add_cog(Who(bot=bot, extension_name="who"))
    bot.add_extension_config("who", config)


class Who(cogs.BaseCog):
    """Class to set up who for the extension.

    Attrs:
        notes (app_commands.Group): The group for the /note commands

    """

    notes = app_commands.Group(
        name="note", description="Command Group for the Notes Extension"
    )

    @staticmethod
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
        if reader_roles := config.extensions.who.note_writers.value:
            roles = (
                discord.utils.get(interaction.guild.roles, name=role)
                for role in reader_roles
            )
            status = any((role in interaction.user.roles for role in roles))
            if not status:
                raise app_commands.MissingAnyRole(reader_roles)
            return True

        # Reader_roles are empty (not set)
        message = "There aren't any `note_writers` roles set in the config!"
        embed = auxiliary.prepare_deny_embed(message=message)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        raise app_commands.AppCommandError(message)

    @staticmethod
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
        if reader_roles := config.extensions.who.note_readers.value:
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
        embed = auxiliary.prepare_deny_embed(message=message)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        raise app_commands.AppCommandError(message)

    @app_commands.check(is_reader)
    @app_commands.command(
        name="whois",
        description="Gets Discord user information",
        extras={"brief": "Gets user data", "usage": "@user", "module": "who"},
    )
    async def get_note(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """This is the base of the /whois command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The member to lookup. Will not work on discord.User
        """
        embed = discord.Embed(
            title=f"User info for `{user}`",
            description="**Note: this is a bot account!**" if user.bot else "",
        )

        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="Created at", value=user.created_at.replace(microsecond=0))
        embed.add_field(name="Joined at", value=user.joined_at.replace(microsecond=0))
        embed.add_field(
            name="Status", value=interaction.guild.get_member(user.id).status
        )
        embed.add_field(name="Nickname", value=user.display_name)

        role_string = ", ".join(role.name for role in user.roles[1:])
        embed.add_field(name="Roles", value=role_string or "No roles")

        # Adds special information only visible to mods
        if interaction.permissions.kick_members:
            embed = await self.modify_embed_for_mods(interaction, user, embed)

        user_notes = await self.get_notes(user, interaction.guild)
        total_notes = 0
        if user_notes:
            total_notes = len(user_notes)
            user_notes = user_notes[:3]
        embed.set_footer(text=f"{total_notes} total notes")
        embed.color = discord.Color.dark_blue()

        for note in user_notes:
            author = interaction.guild.get_member(int(note.author_id)) or note.author_id
            embed.add_field(
                name=f"Note from {author} ({note.updated.date()})",
                value=f"*{note.body}*" or "*None*",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def modify_embed_for_mods(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        embed: discord.Embed,
    ) -> discord.Embed:
        """Makes modifications to the whois embed to add mod only information

        Args:
            interaction (discord.Interaction): The interaction where the /whois command was called
            user (discord.Member): The user being looked up
            embed (discord.Embed): The embed already filled with whois information

        Returns:
            discord.Embed: The embed with mod only information added
        """
        # If the user has warnings, add them
        warnings = (
            await self.bot.models.Warning.query.where(
                self.bot.models.Warning.user_id == str(user.id)
            )
            .where(self.bot.models.Warning.guild_id == str(interaction.guild.id))
            .gino.all()
        )
        warning_str = ""
        for warning in warnings:
            warning_str += f"{warning.reason} - {warning.time.date()}\n"
        if warning_str:
            embed.add_field(
                name="**Warnings**",
                value=warning_str,
                inline=True,
            )

        # If the user has a pending application, show it
        # If the user is banned from making applications, show it
        application_cog = interaction.client.get_cog("ApplicationManager")
        if application_cog:
            has_application = await application_cog.search_for_pending_application(user)
            is_banned = await application_cog.get_ban_entry(user)
            embed.add_field(
                name="Application information:",
                value=(
                    f"Has pending application: {bool(has_application)}\nIs banned from"
                    f" making applications: {bool(is_banned)}"
                ),
                inline=True,
            )
        return embed

    @app_commands.check(is_writer)
    @notes.command(
        name="set",
        description="Sets a note for a user, which can be read later from their whois",
        extras={
            "brief": "Sets a note for a user",
            "usage": "@user [note]",
            "module": "who",
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
        for name in config.extensions.who.note_bypass.value:
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
            interaction.guild.roles, name=config.extensions.who.note_role.value
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

    @app_commands.check(is_writer)
    @notes.command(
        name="clear",
        description="Clears all existing notes for a user",
        extras={
            "brief": "Clears all notes for a user",
            "usage": "@user",
            "module": "who",
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
        notes = await self.get_notes(user, interaction.guild)

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
            interaction.guild.roles, name=config.extensions.who.note_role.value
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
            "module": "who",
        },
    )
    async def all_notes(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Gets a file containing every note on a user
        This is the entrance for the /note all command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The member to get all notes for
        """
        notes = await self.get_notes(user, interaction.guild)

        if not notes:
            embed = auxiliary.prepare_deny_embed(
                message=f"There are no notes for `{user}`"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        note_output_data = []
        for note in notes:
            author = interaction.guild.get_member(int(note.author_id)) or note.author_id
            data = {
                "body": note.body,
                "from": str(author),
                "at": str(note.updated),
            }
            note_output_data.append(data)

        yaml_file = discord.File(
            io.StringIO(yaml.dump({"notes": note_output_data})),
            filename=f"notes-for-{user.id}-{datetime.datetime.utcnow()}.yaml",
        )

        await interaction.response.send_message(file=yaml_file, ephemeral=True)

    async def get_notes(
        self: Self, user: discord.Member, guild: discord.Guild
    ) -> list[bot.models.UserNote]:
        """Calls to the database to get a list of note database entries for a given user and guild

        Args:
            user (discord.Member): The member to look for notes for
            guild (discord.Guild): The guild to fetch the notes from

        Returns:
            list[bot.models.UserNote]: The list of notes on the member/guild combo.
                Will be an empty list if there are no notes
        """
        user_notes = (
            await self.bot.models.UserNote.query.where(
                self.bot.models.UserNote.user_id == str(user.id)
            )
            .where(self.bot.models.UserNote.guild_id == str(guild.id))
            .order_by(self.bot.models.UserNote.updated.desc())
            .gino.all()
        )

        return user_notes

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
            member.guild.roles, name=config.extensions.who.note_role.value
        )
        if not role:
            return

        user_notes = await self.get_notes(member, member.guild)
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
