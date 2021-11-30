import datetime
import random

import base
import discord
import util
from discord.ext import commands


def setup(bot):
    class Grab(bot.db.Model):
        __tablename__ = "grabs"

        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        author_id = bot.db.Column(bot.db.String)
        channel = bot.db.Column(bot.db.String)
        guild = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        nsfw = bot.db.Column(bot.db.Boolean, default=False)

    config = bot.PluginConfig()
    config.add(
        key="per_page",
        datatype="int",
        title="Grabs per page",
        description="The number of grabs per page when retrieving all grabs",
        default=3,
    )
    config.add(
        key="blocked_channels",
        datatype="list",
        title="List of blocked channels",
        description="The list of channels to disable the grabs plugin",
        default=[],
    )

    bot.process_plugin_setup(cogs=[Grabber], models=[Grab], config=config)


class Grabber(base.BaseCog):

    HAS_CONFIG = False
    SEARCH_LIMIT = 20

    # this could probably be a check decorator
    # but oh well
    async def invalid_channel(self, config, ctx):
        if ctx.channel.id in config.plugins.grab.blocked_channels.value:
            await util.send_with_mention(ctx, "Grabs are disabled for this channel")
            return True

        return False

    @util.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @commands.command(
        name="grab",
        brief="Grabs a user's last message",
        description="Gets the last message of the mentioned user and saves it",
        usage="@user",
    )
    async def grab_user(self, ctx, *, user_to_grab: discord.Member):
        config = await self.bot.get_context_config(ctx)

        if await self.invalid_channel(config, ctx):
            return

        if user_to_grab.bot:
            await util.send_with_mention(ctx, "Ain't gonna catch me slipping!")
            return

        grab_message = None
        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user_to_grab:
                grab_message = message.content
                break

        if not grab_message:
            await util.send_with_mention(
                ctx, f"Could not find a recent message from user {user_to_grab}"
            )
            return

        grab = (
            await self.models.Grab.query.where(
                self.models.Grab.author_id == str(user_to_grab.id),
            )
            .where(self.models.Grab.message == grab_message)
            .gino.first()
        )

        if grab:
            await util.send_with_mention(ctx, "That grab already exists!")
            return

        grab = self.models.Grab(
            author_id=str(user_to_grab.id),
            channel=str(ctx.channel.id),
            guild=str(ctx.guild.id),
            message=grab_message,
            nsfw=ctx.channel.is_nsfw(),
        )
        await grab.create()

        await util.send_with_mention(ctx, f"Successfully saved: '*{grab_message}*'")

    @commands.group(
        brief="Executes a grabs command",
        description="Executes a grabs command",
    )
    async def grabs(self, ctx):
        pass

    @util.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @grabs.command(
        name="all",
        brief="Returns grabs for a user",
        description="Returns all grabbed messages for a user",
        usage="@user",
    )
    async def all_grabs(self, ctx, user_to_grab: discord.Member):
        is_nsfw = ctx.channel.is_nsfw()

        config = await self.bot.get_context_config(ctx)

        if await self.invalid_channel(config, ctx):
            return

        if user_to_grab.bot:
            await util.send_with_mention(ctx, "Ain't gonna catch me slipping!")
            return

        query = self.models.Grab.query.where(
            self.models.Grab.author_id == str(user_to_grab.id)
        ).where(self.models.Grab.guild == str(ctx.guild.id))

        if not is_nsfw:
            query = query.where(self.models.Grab.nsfw == False)

        grabs = await query.gino.all()

        if not grabs:
            await util.send_with_mention(ctx, f"No grabs found for {user_to_grab.name}")
            return

        grabs.sort(reverse=True, key=lambda grab: grab.time)

        embeds = []
        field_counter = 1
        for index, grab_ in enumerate(grabs):
            filtered_message = self.bot.sub_mentions_for_usernames(grab_.message)
            description = "Let's take a stroll down memory lane..."
            if not is_nsfw:
                description = "Note: *NSFW grabs are hidden in this channel*"
            embed = (
                discord.Embed(
                    title=f"Grabs for {user_to_grab.name}",
                    description=description,
                )
                if field_counter == 1
                else embed
            )
            embed.add_field(
                name=f'"{filtered_message}"',
                value=grab_.time.date(),
                inline=False,
            )
            if (
                field_counter == config.plugins.grab.per_page.value
                or index == len(list(grabs)) - 1
            ):
                embed.set_thumbnail(url=user_to_grab.avatar_url)
                embed.color = discord.Color.orange()
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        self.bot.task_paginate(ctx, embeds=embeds, restrict=True)

    @util.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @grabs.command(
        name="random",
        brief="Returns a random grab",
        description="Returns a random grabbed message for a user (note: NSFW messages are filtered by channel settings)",
        usage="@user",
    )
    async def random_grab(self, ctx, user_to_grab: discord.Member):
        config = await self.bot.get_context_config(ctx)

        if await self.invalid_channel(config, ctx):
            return

        if user_to_grab.bot:
            await util.send_with_mention(ctx, "Ain't gonna catch me slipping!")
            return

        grabs = (
            await self.models.Grab.query.where(
                self.models.Grab.author_id == str(user_to_grab.id)
            )
            .where(self.models.Grab.guild == str(ctx.guild.id))
            .gino.all()
        )

        query = self.models.Grab.query.where(
            self.models.Grab.author_id == str(user_to_grab.id)
        ).where(self.models.Grab.guild == str(ctx.guild.id))

        if not ctx.channel.is_nsfw():
            query = query.where(self.models.Grab.nsfw == False)

        grabs = await query.gino.all()

        if not grabs:
            await util.send_with_mention(ctx, f"No grabs found for {user_to_grab}")
            return

        random_index = random.randint(0, len(grabs) - 1)
        grab = grabs[random_index]

        filtered_message = self.bot.sub_mentions_for_usernames(grab.message)

        embed = discord.Embed(
            title=f'"{filtered_message}"',
            description=f"{user_to_grab.name}, {grab.time.date()}",
        )

        embed.color = discord.Color.orange()

        embed.set_thumbnail(url=user_to_grab.avatar_url)

        await util.send_with_mention(ctx, embed=embed)
