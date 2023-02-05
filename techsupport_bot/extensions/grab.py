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

    config = bot.ExtensionConfig()
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

    bot.add_cog(Grabber(bot=bot, models=[Grab]))
    bot.add_extension_config("grab", config)


async def invalid_channel(ctx):
    config = await ctx.bot.get_context_config(ctx)

    if ctx.channel.id in config.extensions.grab.blocked_channels.value:
        await ctx.send_deny_embed("Grabs are disabled for this channel")
        return False

    return True


class Grabber(base.BaseCog):
    HAS_CONFIG = False
    SEARCH_LIMIT = 20

    @util.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @commands.command(
        name="grab",
        brief="Grabs a user's message",
        description="Grabs a message by ID and saves it",
        usage="[message-id]",
    )
    async def grab_user(self, ctx, message: discord.Message):
        if message.author.bot:
            await ctx.send_deny_embed("Ain't gonna catch me slipping!")
            return

        grab = (
            await self.models.Grab.query.where(
                self.models.Grab.author_id == str(message.author.id),
            )
            .where(self.models.Grab.message == message.content)
            .gino.first()
        )

        if grab:
            await ctx.send_deny_embed("That grab already exists!")
            return

        grab = self.models.Grab(
            author_id=str(message.author.id),
            channel=str(ctx.channel.id),
            guild=str(ctx.guild.id),
            message=message.clean_content,
            nsfw=ctx.channel.is_nsfw(),
        )
        await grab.create()

        await ctx.send_confirm_embed(f"Successfully saved: '*{message.clean_content}*'")

    @commands.group(
        brief="Executes a grabs command",
        description="Executes a grabs command",
    )
    async def grabs(self, ctx):
        pass

    @util.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @grabs.command(
        name="all",
        brief="Returns grabs for a user",
        description="Returns all grabbed messages for a user",
        usage="@user",
    )
    async def all_grabs(self, ctx, user_to_grab: discord.Member):
        is_nsfw = ctx.channel.is_nsfw()

        config = await self.bot.get_context_config(ctx)

        if user_to_grab.bot:
            await ctx.send_deny_embed("Ain't gonna catch me slipping!")
            return

        query = self.models.Grab.query.where(
            self.models.Grab.author_id == str(user_to_grab.id)
        ).where(self.models.Grab.guild == str(ctx.guild.id))

        if not is_nsfw:
            query = query.where(self.models.Grab.nsfw == False)

        grabs = await query.gino.all()

        if not grabs:
            await ctx.send_deny_embed(f"No grabs found for {user_to_grab.name}")
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
                    title=f"Grabs for {user_to_grab.name}",
                    description=description,
                )
                if field_counter == 1
                else embed
            )
            embed.add_field(
                name=f'"{grab_.message}"',
                value=grab_.time.date(),
                inline=False,
            )
            if (
                field_counter == config.extensions.grab.per_page.value
                or index == len(list(grabs)) - 1
            ):
                embed.set_thumbnail(url=user_to_grab.avatar_url)
                embed.color = discord.Color.orange()
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        ctx.task_paginate(pages=embeds)

    @util.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @grabs.command(
        name="random",
        brief="Returns a random grab",
        description="Returns a random grabbed message for a user (note: NSFW messages are filtered by channel settings)",
        usage="@user",
    )
    async def random_grab(self, ctx, user_to_grab: discord.Member):
        config = await self.bot.get_context_config(ctx)

        if user_to_grab.bot:
            await ctx.send_deny_embed("Ain't gonna catch me slipping!")
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
            await ctx.send_deny_embed(f"No grabs found for {user_to_grab}")
            return

        random_index = random.randint(0, len(grabs) - 1)
        grab = grabs[random_index]

        embed = discord.Embed(
            title=f'"{grab.message}"',
            description=f"{user_to_grab.name}, {grab.time.date()}",
        )

        embed.color = discord.Color.orange()

        embed.set_thumbnail(url=user_to_grab.avatar_url)

        await ctx.send(embed=embed)
