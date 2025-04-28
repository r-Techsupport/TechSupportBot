"""Module for the who extension for the discord bot."""

from __future__ import annotations

import datetime
import io
from typing import TYPE_CHECKING, Self

import discord
import ui
import yaml
from botlogging import LogContext, LogLevel
from commands import moderator, notes
from core import auxiliary, cogs, moderation
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Who plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Whois(bot=bot, extension_name="whois"))


class Whois(cogs.BaseCog):

    @app_commands.command(
        name="whois",
        description="Gets Discord user information",
        extras={"brief": "Gets user data", "usage": "@user", "module": "who"},
    )
    async def whois_command(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """This is the base of the /whois command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The member to lookup. Will not work on discord.User
        """
        embed = auxiliary.generate_basic_embed(
            title=f"User info for `{member.display_name}` (`{member.name}`)",
            description="**Note: this is a bot account!**" if member.bot else "",
            color=discord.Color.dark_blue(),
            url=member.display_avatar.url,
        )

        embed.add_field(
            name="Created at", value=member.created_at.replace(microsecond=0)
        )
        embed.add_field(name="Joined at", value=member.joined_at.replace(microsecond=0))
        embed.add_field(
            name="Status", value=interaction.guild.get_member(member.id).status
        )
        embed.add_field(name="Nickname", value=member.display_name)

        role_string = ", ".join(role.name for role in member.roles[1:])
        embed.add_field(name="Roles", value=role_string or "No roles")

        if interaction.permissions.kick_members:
            embed = await self.modify_embed_for_mods(interaction, member, embed)

        embeds = [embed]

        if await notes.is_reader(interaction):
            all_notes = await moderation.get_all_notes(
                self.bot, member, interaction.guild
            )
            notes_embeds = notes.build_note_embeds(interaction.guild, member, all_notes)
            notes_embeds[0].description = (
                f"Showing {min(len(all_notes), 6)}/{len(all_notes)} notes"
            )
            embeds.append(notes_embeds[0])

        if interaction.permissions.kick_members:
            all_warnings = await moderation.get_all_warnings(
                self.bot, member, interaction.guild
            )
            warning_embeds = moderator.build_warning_embeds(
                interaction.guild, member, all_warnings
            )
            warning_embeds[0].description = (
                f"Showing {min(len(all_warnings), 6)}/{len(all_warnings)} warnings"
            )
            embeds.append(warning_embeds[0])

        await interaction.response.defer(ephemeral=True)
        view = ui.PaginateView()
        await view.send(
            interaction.channel, interaction.user, embeds, interaction, True
        )
        return

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
