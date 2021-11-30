import datetime
import io

import base
import discord
import util
import yaml
from discord.ext import commands


def setup(bot):
    class UserNote(bot.db.Model):
        __tablename__ = "usernote"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        updated = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        author_id = bot.db.Column(bot.db.String)
        body = bot.db.Column(bot.db.String)

    bot.process_plugin_setup(cogs=[Who], models=[UserNote])


class Who(base.BaseCog):

    # whois command
    @commands.command(
        name="whois",
        brief="Gets user data",
        description="Gets Discord user information",
        usage="@user",
    )
    async def whois_user(self, ctx, user: discord.Member):
        embed = discord.Embed(
            title=f"User info for {user}",
            description="**Note: this is a bot account!**" if user.bot else "",
        )

        embed.set_thumbnail(url=user.avatar_url)

        embed.add_field(name="Created at", value=user.created_at)
        embed.add_field(name="Joined at", value=user.joined_at)
        embed.add_field(name="Nickname", value=user.nick, inline=False)
        embed.add_field(name="Status", value=user.status)

        user_notes = await self.get_notes(user, ctx.guild)

        total_notes = 0
        if user_notes:
            total_notes = len(user_notes)
            user_notes = user_notes[-3:]
        embed.set_footer(text=f"{total_notes} total notes")
        embed.color = discord.Color.dark_blue()

        for note in user_notes:
            author = ctx.guild.get_member(int(note.author_id)) or "<Not found>"
            embed.add_field(
                name=f"Note (from {author} at {note.updated})",
                value=f"*{note.body}*" or "*None*",
                inline=False,
            )

        await util.send_with_mention(ctx, embed=embed)

    @commands.has_permissions(kick_members=True)
    @commands.group(
        brief="Executes a note command",
        description="Executes a note command",
    )
    async def note(self, ctx):
        pass

    @note.command(
        name="set",
        brief="Sets a note for a user",
        description="Sets a note for a user, which can be read later from their whois",
        usage="@user [note]",
    )
    async def set_note(self, ctx, user: discord.Member, *, body: str):
        if ctx.author.id == user.id:
            await util.send_with_mention(ctx, "You cannot add a note for yourself")
            return

        note = self.models.UserNote(
            user_id=str(user.id),
            guild_id=str(ctx.guild.id),
            author_id=str(ctx.author.id),
            body=body,
        )

        await note.create()

        await util.send_with_mention(ctx, "I created that note successfully")

    @note.command(
        name="clear",
        brief="Clears all notes for a user",
        description="Clears all existing notes for a user",
        usage="@user",
    )
    async def clear_notes(self, ctx, user: discord.Member):
        notes = await self.get_notes(user, ctx.guild)

        if not notes:
            await util.send_with_mention(ctx, "There are no notes for that user")
            return

        await self.bot.confirm(
            ctx,
            f"Are you sure you want to clear {len(notes)} notes?",
            delete_after=True,
        )

        for note in notes:
            await note.delete()

        await util.send_with_mention(ctx, "I cleared all the notes for that user")

    @note.command(
        name="all",
        brief="Gets all notes for a user",
        description="Gets all notes for a user instead of just new ones",
        usage="@user",
    )
    async def all_notes(self, ctx, user: discord.Member):
        notes = await self.get_notes(user, ctx.guild)

        if not notes:
            await util.send_with_mention(ctx, "There are no notes for that user")
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

        await util.send_with_mention(ctx, file=yaml_file)

    async def get_notes(self, user, guild):
        user_notes = (
            await self.models.UserNote.query.where(
                self.models.UserNote.user_id == str(user.id)
            )
            .where(self.models.UserNote.guild_id == str(guild.id))
            .gino.all()
        )

        user_notes.sort(key=lambda u: u.updated)

        return user_notes
