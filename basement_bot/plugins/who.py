import datetime

import base
import discord
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
    @commands.has_permissions(kick_members=True)
    @commands.command(
        name="whois",
        brief="Gets user data",
        description="Gets Discord user information",
        usage="@user",
    )
    async def whois_user(self, ctx, user: discord.Member):
        embed = discord.Embed(
            title=f"User info for {user}",
            description="**Note: this user is a bot!**" if user.bot else "",
        )

        embed.set_thumbnail(url=user.avatar_url)

        embed.add_field(name="Created at", value=user.created_at)
        embed.add_field(name="Joined at", value=user.joined_at)
        embed.add_field(name="Nickname", value=user.nick, inline=False)
        embed.add_field(name="Status", value=user.status)

        user_notes = await self.get_notes(user, ctx.guild)

        if user_notes:
            user_notes = user_notes[-3:]

        for note in user_notes:
            author = ctx.guild.get_member(int(note.author_id))
            embed.add_field(
                name=f"Note (from {author} at {note.updated})",
                value=f"*{note.body}*" or "*None*",
                inline=False,
            )

        await self.bot.send_with_mention(ctx, embed=embed)

    @commands.group(
        brief="Executes a note command",
        description="Executes a note command",
    )
    async def note(self, ctx):
        pass

    @commands.has_permissions(kick_members=True)
    @note.command(
        name="set",
        brief="Sets a note for a user",
        description="Sets a note for a user, which can be read later from their whois",
        usage="@user [note]",
    )
    async def set_note(self, ctx, user: discord.Member, *, body: str):
        if ctx.author.id == user.id:
            await self.bot.send_with_mention(ctx, "You cannot add a note for yourself")

        note = self.models.UserNote(
            user_id=str(user.id),
            guild_id=str(ctx.guild.id),
            author_id=str(ctx.author.id),
            body=body,
        )

        await note.create()

        await self.bot.send_with_mention(ctx, "I created that note successfully")

    @commands.has_permissions(kick_members=True)
    @note.command(
        name="clear",
        brief="Clears all notes for a user",
        description="Clears all existing notes for a user",
        usage="@user",
    )
    async def clear_notes(self, ctx, user: discord.Member):
        notes = await self.get_notes(user, ctx.guild)

        for note in notes:
            await note.delete()

        await self.bot.send_with_mention(ctx, "I cleared all the notes for that user")

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
