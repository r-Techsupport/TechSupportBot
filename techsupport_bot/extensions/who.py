"""Module for the who extension for the discord bot."""
import datetime
import io

import base
import discord
import ui
import yaml
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Adding the who configuration to the config file."""

    class UserNote(bot.db.Model):
        """Class to set up the config file."""

        __tablename__ = "usernote"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        updated = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        author_id = bot.db.Column(bot.db.String)
        body = bot.db.Column(bot.db.String)

    class Warning(bot.db.Model):
        """Class to set up warnings for the config file."""

        __tablename__ = "warnings"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        reason = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    config = bot.ExtensionConfig()
    config.add(
        key="note_role",
        datatype="int",
        title="Note role",
        description="The name of the role to be added when a note is added to a user",
        default=None,
    )
    config.add(
        key="note_bypass",
        datatype="list",
        title="Note bypass list",
        description="A list of roles that shouldn't have notes set or the note roll assigned",
        default=["Moderator"],
    )

    await bot.add_cog(Who(bot=bot, models=[UserNote, Warning], extension_name="who"))
    bot.add_extension_config("who", config)


class Who(base.BaseCog):
    """Class to set up who for the extension."""

    # whois command
    @commands.command(
        name="whois",
        brief="Gets user data",
        description="Gets Discord user information",
        usage="@user",
    )
    async def whois_user(self, ctx, user: discord.Member):
        """Method to set up the embed for the user."""
        embed = discord.Embed(
            title=f"User info for `{user}`",
            description="**Note: this is a bot account!**" if user.bot else "",
        )

        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="Created at", value=user.created_at.replace(microsecond=0))
        embed.add_field(name="Joined at", value=user.joined_at.replace(microsecond=0))
        embed.add_field(name="Status", value=user.status)
        embed.add_field(name="Nickname", value=user.nick)

        role_string = ", ".join(role.name for role in user.roles[1:])
        embed.add_field(name="Roles", value=role_string or "No roles")

        # Gets all warnings for an user and adds them to the embed (Mod only)
        if ctx.permissions.kick_members:
            warnings = (
                await self.models.Warning.query.where(
                    self.models.Warning.user_id == str(user.id)
                )
                .where(self.models.Warning.guild_id == str(ctx.guild.id))
                .gino.all()
            )
            for warning in warnings:
                embed.add_field(
                    name=f"**Warning ({warning.time.date()})**",
                    value=f"*{warning.reason}*",
                    inline=False,
                )

        user_notes = await self.get_notes(user, ctx.guild)
        total_notes = 0
        if user_notes:
            total_notes = len(user_notes)
            user_notes = user_notes[:3]
        embed.set_footer(text=f"{total_notes} total notes")
        embed.color = discord.Color.dark_blue()

        for note in user_notes:
            author = ctx.guild.get_member(int(note.author_id)) or "<Not found>"
            embed.add_field(
                name=f"Note from {author} ({note.updated.date()})",
                value=f"*{note.body}*" or "*None*",
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.has_permissions(kick_members=True)
    @commands.group(
        brief="Executes a note command",
        description="Executes a note command",
    )
    async def note(self, ctx):
        """Method for the note command."""

        # Executed if there are no/invalid args supplied
        await base.extension_help(self, ctx, self.__module__[11:])

        pass

    @note.command(
        name="set",
        brief="Sets a note for a user",
        description="Sets a note for a user, which can be read later from their whois",
        usage="@user [note]",
    )
    async def set_note(self, ctx, user: discord.Member, *, body: str):
        """Method to set a note on a user."""
        if ctx.author.id == user.id:
            await auxiliary.send_deny_embed(
                message="You cannot add a note for yourself", channel=ctx.channel
            )
            return

        note = self.models.UserNote(
            user_id=str(user.id),
            guild_id=str(ctx.guild.id),
            author_id=str(ctx.author.id),
            body=body,
        )

        config = await self.bot.get_context_config(ctx)

        # Check to make sure notes are allowed to be assigned
        for name in config.extensions.who.note_bypass.value:
            role_check = discord.utils.get(ctx.guild.roles, name=name)
            if not role_check:
                continue
            if role_check in getattr(user, "roles", []):
                await auxiliary.send_deny_embed(
                    message=f"You cannot assign notes to `{user}` because "
                    + f"they have `{role_check}` role",
                    channel=ctx.channel,
                )
                return

        await note.create()

        role = discord.utils.get(
            ctx.guild.roles, name=config.extensions.who.note_role.value
        )

        if not role:
            await auxiliary.send_confirm_embed(
                message=f"Note created for `{user}`, but no note "
                + "role is configured so no role was added",
                channel=ctx.channel,
            )
            return

        await user.add_roles(role)

        await auxiliary.send_confirm_embed(
            message=f"Note created for `{user}`", channel=ctx.channel
        )

    @note.command(
        name="clear",
        brief="Clears all notes for a user",
        description="Clears all existing notes for a user",
        usage="@user",
    )
    async def clear_notes(self, ctx, user: discord.Member):
        """Method to clear notes on a user."""
        notes = await self.get_notes(user, ctx.guild)

        if not notes:
            await auxiliary.send_deny_embed(
                message="There are no notes for that user", channel=ctx.channel
            )
            return

        view = ui.Confirm()
        await view.send(
            message=f"Are you sure you want to clear {len(notes)} notes?",
            channel=ctx.channel,
            author=ctx.author,
        )

        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                message=f"Notes for `{user}` were not cleared", channel=ctx.channel
            )
            return

        for note in notes:
            await note.delete()

        config = await self.bot.get_context_config(ctx)
        role = discord.utils.get(
            ctx.guild.roles, name=config.extensions.who.note_role.value
        )
        if role:
            await user.remove_roles(role)

        await auxiliary.send_confirm_embed(
            message=f"Notes cleared for `{user}`", channel=ctx.channel
        )

    @note.command(
        name="all",
        brief="Gets all notes for a user",
        description="Gets all notes for a user instead of just new ones",
        usage="@user",
    )
    async def all_notes(self, ctx, user: discord.Member):
        """Method to get all notes for a user."""
        notes = await self.get_notes(user, ctx.guild)

        if not notes:
            await auxiliary.send_deny_embed(
                message=f"There are no notes for `{user}`", channel=ctx.channel
            )
            return

        note_output_data = []
        for note in notes:
            author = ctx.guild.get_member(int(note.author_id)) or "<Not found>"
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

        await ctx.send(file=yaml_file)

    async def get_notes(self, user, guild):
        """Method to get current notes on the user."""
        user_notes = (
            await self.models.UserNote.query.where(
                self.models.UserNote.user_id == str(user.id)
            )
            .where(self.models.UserNote.guild_id == str(guild.id))
            .order_by(self.models.UserNote.updated.desc())
            .gino.all()
        )

        return user_notes

    # re-adds note role back to joining users
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Method to get the member on joining the guild."""
        config = await self.bot.get_context_config(guild=member.guild)
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

        await member.add_roles(role)

        await self.bot.guild_log(
            member.guild,
            "logging_channel",
            "warning",
            f"Found noted user with ID {member.id} joining - re-adding role",
            send=True,
        )
