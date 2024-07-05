"""
Module for defining the grabs extension
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
import ui
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Grab plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

    config = extensionconfig.ExtensionConfig()
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

    await bot.add_cog(Grabber(bot=bot))
    bot.add_extension_config("grab", config)


async def invalid_channel(ctx: commands.Context) -> bool:
    """A method to check channels against the whitelist
    If the channel is not in the whitelist, the command execution is halted
    This is expected to be used in a @commands.check call

    Args:
        ctx (commands.Context): The context in which the command was run in

    Raises:
        CommandError: Raised if grabs aren't allowed in the given channel

    Returns:
        bool: If the grabs are allowed in the channel the command was run in
    """

    config = ctx.bot.guild_configs[str(ctx.guild.id)]
    # Check if list is empty. If it is, allow all channels
    if not config.extensions.grab.allowed_channels.value:
        return True
    # If this list is not empty, it is a strict whitelist
    if str(ctx.channel.id) in config.extensions.grab.allowed_channels.value:
        return True
    raise commands.CommandError("Grabs are disabled for this channel")


class Grabber(cogs.BaseCog):
    """Class for the actual commands

    Attrs:
        SEARCH_LIMIT (int): The max amount of messages to search when grabbing
    """

    SEARCH_LIMIT = 20

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @commands.command(
        name="grab",
        brief="Grabs a user's message",
        description="Grabs a message by ID and saves it",
        usage="[username-or-user-ID]",
    )
    async def grab_user(
        self: Self, ctx: commands.Context, user_to_grab: discord.Member
    ) -> None:
        """This is the grab by user function. Accessible by .grab
        This will only search for 20 messages

        Args:
            ctx (commands.Context): The context in which the command was run in
            user_to_grab (discord.Member): The user to search for grabs from
        """

        if user_to_grab.bot:
            await auxiliary.send_deny_embed(
                message="Ain't gonna catch me slipping!", channel=ctx.channel
            )
            return

        if user_to_grab == ctx.author:
            await auxiliary.send_deny_embed(
                message="You can't do this to yourself", channel=ctx.channel
            )
            return

        grab_message = None

        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user_to_grab:
                grab_message = message.content
                break

        if not grab_message:
            await auxiliary.send_deny_embed(
                message=f"Could not find a recent message from user {user_to_grab}",
                channel=ctx.channel,
            )
            return

        grab = (
            await self.bot.models.Grab.query.where(
                self.bot.models.Grab.author_id == str(user_to_grab.id),
            )
            .where(self.bot.models.Grab.message == grab_message)
            .gino.first()
        )

        if grab:
            await auxiliary.send_deny_embed(
                message="That grab already exists!", channel=ctx.channel
            )
            return

        grab = self.bot.models.Grab(
            author_id=str(user_to_grab.id),
            channel=str(ctx.channel.id),
            guild=str(ctx.guild.id),
            message=grab_message,
            nsfw=ctx.channel.is_nsfw(),
        )
        await grab.create()

        await auxiliary.send_confirm_embed(
            message=f"Successfully saved: '*{grab_message}*'", channel=ctx.channel
        )

    @commands.group(
        brief="Executes a grabs command",
        description="Executes a grabs command",
    )
    async def grabs(self: Self, ctx: commands.Context) -> None:
        """The bare .grabs command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @grabs.command(
        name="all",
        brief="Returns grabs for a user",
        description="Returns all grabbed messages for a user",
        usage="[user]",
    )
    async def all_grabs(
        self: Self, ctx: commands.Context, user_to_grab: discord.Member
    ) -> None:
        """Discord command to get a paginated list of all grabs from a given user

        Args:
            ctx (commands.Context): The context in which the command was run in
            user_to_grab (discord.Member): The user to get all the grabs from
        """
        is_nsfw = ctx.channel.is_nsfw()

        config = self.bot.guild_configs[str(ctx.guild.id)]

        if user_to_grab.bot:
            await auxiliary.send_deny_embed(
                message="Ain't gonna catch me slipping!", channel=ctx.channel
            )
            return

        query = self.bot.models.Grab.query.where(
            self.bot.models.Grab.author_id == str(user_to_grab.id)
        ).where(self.bot.models.Grab.guild == str(ctx.guild.id))

        if not is_nsfw:
            # pylint: disable=C0121
            query = query.where(self.bot.models.Grab.nsfw == False)

        grabs = await query.gino.all()

        if not grabs:
            await auxiliary.send_deny_embed(
                message=f"No grabs found for {user_to_grab.name}", channel=ctx.channel
            )
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

        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @grabs.command(
        name="random",
        brief="Returns a random grab",
        description="Returns a random grabbed message for a user "
        + "(note: NSFW messages are filtered by channel settings)",
        usage="[user]",
    )
    async def random_grab(
        self: Self, ctx: commands.Context, user_to_grab: discord.Member
    ) -> None:
        """Discord command to get a random grab from the given user

        Args:
            ctx (commands.Context): The context in which the command was run in
            user_to_grab (discord.Member): The user to get a random grab from
        """

        if user_to_grab.bot:
            await auxiliary.send_deny_embed(
                message="Ain't gonna catch me slipping!", channel=ctx.channel
            )
            return

        grabs = (
            await self.bot.models.Grab.query.where(
                self.bot.models.Grab.author_id == str(user_to_grab.id)
            )
            .where(self.bot.models.Grab.guild == str(ctx.guild.id))
            .gino.all()
        )

        query = self.bot.models.Grab.query.where(
            self.bot.models.Grab.author_id == str(user_to_grab.id)
        ).where(self.bot.models.Grab.guild == str(ctx.guild.id))

        if not ctx.channel.is_nsfw():
            query = query.where(self.bot.models.Grab.nsfw is False)

        grabs = await query.gino.all()

        if not grabs:
            await auxiliary.send_deny_embed(
                message=f"No grabs found for {user_to_grab}", channel=ctx.channel
            )
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

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.check(invalid_channel)
    @grabs.command(
        name="delete",
        brief="Deleted a specific grab",
        description="Deleted a specific grab from a user by the message",
        usage="[user] [message]",
    )
    async def delete_grab(
        self: Self, ctx: commands.Context, target_user: discord.Member, *, message: str
    ) -> None:
        """Deletes a given grab by exact string

        Args:
            ctx (commands.Context): The context in which the command was run in
            target_user (discord.Member): The user to delete a grab from
            message (str): The exact string of the grab to delete

        Raises:
            CommandError: Raised if the grab cannot be found for the given user
        """
        # Stop execution if the invoker isn't the target or an admin
        if (
            not ctx.message.author.id == target_user.id
            and not ctx.message.author.guild_permissions.administrator
        ):
            await auxiliary.send_deny_embed(
                message="You don't have sufficient permissions to do this!",
                channel=ctx.channel,
            )
            return
        # Gets the target grab by the message
        grab = (
            await self.bot.models.Grab.query.where(
                self.bot.models.Grab.author_id == str(target_user.id)
            )
            .where(self.bot.models.Grab.guild == str(ctx.guild.id))
            .where(self.bot.models.Grab.message == message)
            .gino.all()
        )

        if not grab:
            await auxiliary.send_deny_embed(
                message=f"Grab `{message}` not found for {target_user}",
                channel=ctx.channel,
            )
            return
        try:
            await grab[0].delete()

        except IndexError:
            raise commands.CommandError("Couldn't delete the grab!") from IndexError

        await auxiliary.send_confirm_embed(
            message="Grab succesfully deleted!", channel=ctx.channel
        )
