import datetime
import random

import cogs
import decorate
import discord
import sqlalchemy
from discord.ext import commands


class Grab(cogs.DatabasePlugin.get_base()):
    __tablename__ = "grabs"

    pk = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    author_id = sqlalchemy.Column(sqlalchemy.String)
    channel = sqlalchemy.Column(sqlalchemy.String)
    message = sqlalchemy.Column(sqlalchemy.String)
    time = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.utcnow)


def setup(bot):
    bot.add_cog(Grabber(bot))


class Grabber(cogs.DatabasePlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False
    SEARCH_LIMIT = 20
    MODEL = Grab

    # this could probably be a check decorator
    # but oh well
    async def invalid_channel(self, ctx):
        if ctx.channel.id in self.config.invalid_channels:
            await self.tagged_response(ctx, "Grabs are disabled for this channel")
            return True

        return False

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.command(
        name="grab",
        brief="Grabs a user's last message",
        description="Gets the last message of the mentioned user and saves it",
        usage="@user",
    )
    async def grab_user(self, ctx, user_to_grab: discord.Member):
        if await self.invalid_channel(ctx):
            return

        if user_to_grab.bot:
            await self.tagged_response(ctx, "Ain't gonna catch me slipping!")
            return

        grab_message = None
        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user_to_grab and not message.content.startswith(
                f"{self.bot.config.main.required.command_prefix}grab"
            ):
                grab_message = message.content
                break

        if not grab_message:
            await self.tagged_response(
                ctx, f"Could not find a recent essage from user {user_to_grab}"
            )
            return

        db = self.db_session()

        grab = (
            db.query(Grab)
            .filter(
                Grab.author_id == str(user_to_grab.id),
                Grab.message == grab_message,
            )
            .first()
        )

        if grab:
            await self.tagged_response(ctx, "That grab already exists!")
        else:
            db.add(
                Grab(
                    author_id=str(user_to_grab.id),
                    channel=str(ctx.channel.id),
                    message=grab_message,
                )
            )
            db.commit()
            await self.tagged_response(ctx, f"Successfully saved: '*{grab_message}*'")

        db.close()

    @commands.group(
        brief="Executes a grabs command",
        description="Executes a grabs command",
    )
    async def grabs(self, ctx):
        pass

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @grabs.command(
        brief="Returns grabs for a user",
        description="Returns all grabbed messages for a user",
        usage="@user",
    )
    async def all(self, ctx, user_to_grab: discord.Member):
        if await self.invalid_channel(ctx):
            return

        if user_to_grab.bot:
            await self.tagged_response(ctx, "Ain't gonna catch me slipping!")
            return

        db = self.db_session()

        grabs = (
            db.query(Grab)
            .order_by(Grab.time.desc())
            .filter(Grab.author_id == str(user_to_grab.id))
        ).all()
        for grab in grabs:
            db.expunge(grab)
        db.close()

        if not grabs:
            await self.tagged_response(ctx, f"No grabs found for {user_to_grab.name}")
            return

        embed = self.bot.embed_api.Embed(
            title=f"Grabs for {user_to_grab.name}",
            description=f"Let's take a stroll down memory lane...",
        )
        embed.set_thumbnail(url=user_to_grab.avatar_url)
        embeds = []
        field_counter = 1
        for index, grab_ in enumerate(grabs):
            filtered_message = self.sub_mentions_for_usernames(grab_.message)
            embed = (
                self.bot.embed_api.Embed(
                    title=f"Grabs for {user_to_grab.name}",
                    description=f"Let's take a stroll down memory lane...",
                )
                if field_counter == 1
                else embed
            )
            embed.add_field(
                name=f'"{filtered_message}"',
                value=grab_.time.date(),
                inline=False,
            )
            if field_counter == self.config.grabs_max or index == len(list(grabs)) - 1:
                embed.set_thumbnail(url=user_to_grab.avatar_url)
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        self.task_paginate(ctx, embeds=embeds, restrict=True)

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @grabs.command(
        name="random",
        brief="Returns a random grab",
        description="Returns a random grabbed message for a user",
        usage="@user",
    )
    async def random_grab(self, ctx, user_to_grab: discord.Member):
        if await self.invalid_channel(ctx):
            return

        if user_to_grab.bot:
            await self.tagged_response(ctx, "Ain't gonna catch me slipping!")
            return

        db = self.db_session()

        grabs = db.query(Grab).filter(Grab.author_id == str(user_to_grab.id)).all()

        for grab in grabs:
            db.expunge(grab)
        db.close()

        if not grabs:
            await self.tagged_response(f"No grabs found for {user_to_grab}")
            return

        random_index = random.randint(0, len(grabs) - 1)
        grab = grabs[random_index]

        filtered_message = self.sub_mentions_for_usernames(grab.message)

        embed = self.bot.embed_api.Embed(
            title=f'"{filtered_message}"',
            description=f"{user_to_grab.name}, {grab.time.date()}",
        )

        embed.set_thumbnail(url=user_to_grab.avatar_url)

        await self.tagged_response(ctx, embed=embed)
