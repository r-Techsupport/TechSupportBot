"""
Module for defining the grabs extension
"""
import datetime
import random

import base
import discord
import util
from discord.ext import commands


async def setup(bot):
    """Setup to add Grab to the config file"""

    class Grab(bot.db.Model):
        """Template for a Grab"""

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
        key="allowed_channels",
        datatype="list",
        title="List of allowed channels",
        description="The list of channels to enable the grabs plugin",
        default=[],
    )

    await bot.add_cog(Grabber(bot=bot, models=[Grab]))
    bot.add_extension_config("grab", config)


async def invalid_channel(ctx):
    """
    A method to check channels against the whitelist
    If the channel is not in the whitelist, the command execution is halted

    This is expected to be used in a @commands.check call
    """
    config = await ctx.bot.get_context_config(ctx)
    if str(ctx.channel.id) in config.extensions.grab.allowed_channels.value:
        return True
    raise commands.CommandError("Grabs are disabled for this channel")


class Grabber(base.BaseCog):
    """Class for the actual commands"""

    HAS_CONFIG = False
    SEARCH_LIMIT = 20

    @util.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @commands.command(
        name="grab",
        brief="Grabs a user's message",
        description="Grabs a message by ID and saves it",
        usage="[username-or-user-ID]",
    )
    async def grab_user(self, ctx, user_to_grab: discord.Member):
        """
        This is the grab by user function. Accessible by .grab
        This will only search for 20 messages

        Parameters:
        user_to_grab: discord.Member. The user to search for grabs from
        """
        if user_to_grab.bot:
            await ctx.send_deny_embed("Ain't gonna catch me slipping!")
            return

        if user_to_grab == ctx.author:
            await ctx.send_deny_embed("You can't do this to yourself")
            return

        grab_message = None

        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user_to_grab:
                grab_message = message.content
                break

        if not grab_message:
            await ctx.send_deny_embed(
                f"Could not find a recent message from user {user_to_grab}"
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
            await ctx.send_deny_embed("That grab already exists!")
            return

        grab = self.models.Grab(
            author_id=str(user_to_grab.id),
            channel=str(ctx.channel.id),
            guild=str(ctx.guild.id),
            message=grab_message,
            nsfw=ctx.channel.is_nsfw(),
        )
        await grab.create()

        await ctx.send_confirm_embed(f"Successfully saved: '*{grab_message}*'")

    @commands.group(
        brief="Executes a grabs command",
        description="Executes a grabs command",
    )
    async def grabs(self, ctx):
        """Makes the .grab command group"""
        # Executed if there are no/invalid args supplied
        await base.extension_help(self, ctx, self.__module__[11:])

    @util.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @grabs.command(
        name="all",
        brief="Returns grabs for a user",
        description="Returns all grabbed messages for a user",
        usage="[user]",
    )
    async def all_grabs(self, ctx, user_to_grab: discord.Member):
        """Lists all grabs for an user"""
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
                embed.set_thumbnail(url=user_to_grab.display_avatar.url)
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
        description="Returns a random grabbed message for a user "
        + "(note: NSFW messages are filtered by channel settings)",
        usage="[user]",
    )
    async def random_grab(self, ctx, user_to_grab: discord.Member):
        """Gets a random grab from an user"""

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

        embed.set_thumbnail(url=user_to_grab.display_avatar.url)

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @grabs.command(
        name="delete",
        brief="Deleted a specific grab",
        description="Deleted a specific grab from a user by the message",
        usage="[user] [message]",
    )
    async def delete_grab(self, ctx, target_user: discord.Member, *, message: str):
        """Deletes a specific grab from an user"""
        # Stop execution if the invoker isn't the target or an admin
        if (
            not ctx.message.author.id == target_user.id
            and not ctx.message.author.guild_permissions.administrator
        ):
            await ctx.send_deny_embed(
                "You don't have sufficient permissions to do this!"
            )
            return
        # Gets the target grab by the message
        grab = (
            await self.models.Grab.query.where(
                self.models.Grab.author_id == str(target_user.id)
            )
            .where(self.models.Grab.guild == str(ctx.guild.id))
            .where(self.models.Grab.message == message)
            .gino.all()
        )

        if not grab:
            await ctx.send_deny_embed(f"Grab `{message}` not found for {target_user}")
            return
        try:
            await grab[0].delete()

        except IndexError:
            raise commands.CommandError("Couldn't delete the grab!") from IndexError

        await ctx.send_confirm_embed("Grab succesfully deleted!")
