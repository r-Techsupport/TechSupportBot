"""Module for the duck extension"""

from __future__ import annotations

import asyncio
import datetime
import functools
import random
from datetime import timedelta
from typing import TYPE_CHECKING, Self

import discord
import munch
import ui
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, extensionconfig
from discord import Color as embed_colors
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Duck plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

    config = extensionconfig.ExtensionConfig()
    config.add(
        key="hunt_channels",
        datatype="list",
        title="DuckHunt Channel IDs",
        description="The IDs of the channels the duck should appear in",
        default=[],
    )
    config.add(
        key="min_wait",
        datatype="int",
        title="Min wait (hours)",
        description="The minimum number of hours to wait between duck events",
        default=2,
    )
    config.add(
        key="max_wait",
        datatype="int",
        title="Max wait (hours)",
        description="The maximum number of hours to wait between duck events",
        default=4,
    )
    config.add(
        key="timeout",
        datatype="int",
        title="Duck timeout (seconds)",
        description="The amount of time before the duck disappears",
        default=60,
    )
    config.add(
        key="cooldown",
        datatype="int",
        title="Duck cooldown (seconds)",
        description="The amount of time to wait between bef/bang messages",
        default=5,
    )
    config.add(
        key="success_rate",
        datatype="int",
        title="Success rate (percent %)",
        description="The success rate of bef/bang messages",
        default=50,
    )
    config.add(
        key="spawn_user",
        datatype="list[int]",
        title="Allow user to spawn duck",
        description="Set up who you want to allow to spawn a duck",
        default=[],
    )
    config.add(
        key="allow_manipulation",
        datatype="bool",
        title="Whether or not user manipulation is allowed",
        description="Controls whether release, donate, or kill commands are enabled",
        default=True,
    )

    await bot.add_cog(DuckHunt(bot=bot, extension_name="duck"))
    bot.add_extension_config("duck", config)


class DuckHunt(cogs.LoopCog):
    """Class for the actual duck commands"""

    DUCK_PIC_URL = "https://cdn.icon-icons.com/icons2/1446/PNG/512/22276duck_98782.png"
    BEFRIEND_URL = (
        "https://cdn.icon-icons.com/icons2/603/PNG/512/"
        + "heart_love_valentines_relationship_dating_date_icon-icons.com_55985.png"
    )
    KILL_URL = "https://cdn.icon-icons.com/icons2/1919/PNG/512/huntingtarget_122049.png"
    ON_START = False
    CHANNELS_KEY = "hunt_channels"

    async def loop_preconfig(self: Self) -> None:
        """Preconfig for cooldowns"""
        self.cooldowns = {}

    async def wait(self: Self, config: munch.Munch, _: discord.Guild) -> None:
        """Waits a random amount of time before sending another duck
        This function shouldn't be manually called

        Args:
            config (munch.Munch): The guild config to use to determine the min and max wait times
        """
        await asyncio.sleep(
            random.randint(
                config.extensions.duck.min_wait.value * 3600,
                config.extensions.duck.max_wait.value * 3600,
            )
        )

    async def execute(
        self: Self,
        config: munch.Munch,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
        banned_user: discord.User = None,
    ) -> None:
        """Sends a duck in the given channel
        Can be manually called, and will be called automatically after wait()

        Args:
            config (munch.Munch): The config of the guild where the duck is going
            guild (discord.Guild): The guild where the duck is going
            channel (discord.abc.Messageable): The channel to spawn the duck in
            banned_user (discord.User, optional): A user that is not allowed to claim the duck.
                Defaults to None.
        """
        if not channel:
            config = self.bot.guild_configs[str(guild.id)]
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message="Channel not found for Duckhunt loop - continuing",
                level=LogLevel.WARNING,
                context=LogContext(guild=guild),
                channel=log_channel,
            )
            return

        self.cooldowns[guild.id] = {}

        embed = discord.Embed(
            title="*Quack Quack*",
            description="Befriend the duck with `bef` or shoot with `bang`",
        )
        embed.set_image(url=self.DUCK_PIC_URL)
        embed.color = discord.Color.green()

        duck_message = await channel.send(embed=embed)
        start_time = duck_message.created_at

        response_message = None
        try:
            response_message = await self.bot.wait_for(
                "message",
                timeout=config.extensions.duck.timeout.value,
                # can't pull the config in a non-coroutine
                check=functools.partial(
                    self.message_check, config, channel, duck_message, banned_user
                ),
            )
        except asyncio.TimeoutError:
            pass
        except Exception as exception:
            config = self.bot.guild_configs[str(guild.id)]
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message="Exception thrown waiting for duckhunt input",
                level=LogLevel.ERROR,
                context=LogContext(guild=guild, channel=channel),
                channel=log_channel,
                exception=exception,
            )

        await duck_message.delete()

        if response_message:
            raw_duration = response_message.created_at - start_time
            action = (
                "befriended" if response_message.content.lower() == "bef" else "killed"
            )
            await self.handle_winner(
                response_message.author, guild, action, raw_duration, channel
            )
        else:
            await self.got_away(channel)

    async def got_away(self: Self, channel: discord.TextChannel) -> None:
        """Sends a message telling everyone the duck got away

        Args:
            channel (discord.TextChannel): The channel that the duck was previously in
        """
        embed = discord.Embed(
            title="A duck got away!",
            description="Then he waddled away, waddle waddle, 'til the very next day",
        )
        embed.color = discord.Color.red()

        await channel.send(embed=embed)

    async def handle_winner(
        self,
        winner: discord.Member,
        guild: discord.Guild,
        action: str,
        raw_duration: datetime.datetime,
        channel: discord.abc.Messageable,
    ) -> None:
        """
        This is a function to update the database based on a winner

        Parameters:
        winner -> A discord.Member object for the winner
        guild -> A discord.Guild object for the guild the winner is a part of
        action -> A string, either "befriended" or "killed", depending on the action
        raw_duration -> A datetime object of the time since the duck spawned
        channel -> The channel in which the duck game happened in
        """
        config_ = self.bot.guild_configs[str(guild.id)]
        log_channel = config_.get("logging_channel")
        await self.bot.logger.send_log(
            message=f"Duck {action} by {winner} in #{channel.name}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild, channel=channel),
            channel=log_channel,
        )

        duration_seconds = raw_duration.seconds
        duration_exact = float(
            str(raw_duration.seconds) + "." + str(raw_duration.microseconds)
        )

        duck_user = await self.get_duck_user(winner.id, guild.id)
        if not duck_user:
            duck_user = self.bot.models.DuckUser(
                author_id=str(winner.id),
                guild_id=str(guild.id),
                befriend_count=0,
                kill_count=0,
                speed_record=80.0,
            )
            await duck_user.create()

        if action == "befriended":
            await duck_user.update(befriend_count=duck_user.befriend_count + 1).apply()
        else:
            await duck_user.update(kill_count=duck_user.kill_count + 1).apply()

        await duck_user.update(updated=datetime.datetime.now()).apply()

        embed = discord.Embed(
            title=f"Duck {action}!",
            description=(
                f"{winner.mention} {action} the duck in {duration_seconds} seconds!"
            ),
        )
        embed.color = (
            embed_colors.blurple() if action == "befriended" else embed_colors.red()
        )
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        embed.set_thumbnail(
            url=self.BEFRIEND_URL if action == "befriended" else self.KILL_URL
        )
        global_record = await self.get_global_record(guild.id)
        footer_string = ""
        if duration_exact < duck_user.speed_record:
            footer_string += f"New personal record: {duration_exact} seconds."
            if duration_exact < global_record:
                footer_string += "\nNew global record!"
                footer_string += f" Previous global record: {global_record} seconds"
            await duck_user.update(speed_record=duration_exact).apply()
        else:
            footer_string += f"Exact time: {duration_exact} seconds."
        embed.set_footer(text=footer_string)

        await channel.send(embed=embed)

    def pick_quote(self) -> str:
        """Method for picking a random quote for the miss message"""
        QUOTES_FILE = "resources/duckQuotes.txt"
        with open(QUOTES_FILE, "r", encoding="utf-8") as file:
            lines = file.readlines()
            random_line = random.choice(lines)
            return random_line.strip()

    def message_check(
        self: Self,
        config: munch.Munch,
        channel: discord.abc.GuildChannel,
        duck_message: discord.Message,
        banned_user: discord.User,
        message: discord.Message,
    ) -> bool:
        """Checks if a message after the duck is a valid call to own the duck

        Args:
            config (munch.Munch): The config of the guild where the duck is
            channel (discord.abc.GuildChannel): The channel that the duck is in
            duck_message (discord.Message): The message object of the duck embed
            banned_user (discord.User): A user who is banned from claiming the duck
            message (discord.Message): The raw message that was sent

        Returns:
            bool: Whether the user should claim the duck or not
        """
        # ignore other channels
        if message.channel.id != channel.id:
            return False

        if duck_message.created_at > message.created_at:
            return False

        if not message.content.lower() in ["bef", "bang"]:
            return False

        if banned_user and message.author == banned_user:
            embed = auxiliary.prepare_deny_embed("You cannot hunt a duck you released")
            asyncio.create_task(channel.send(content=banned_user.mention, embed=embed))
            return False

        cooldowns = self.cooldowns.get(message.guild.id, {})

        if (
            datetime.datetime.now()
            - cooldowns.get(message.author.id, datetime.datetime.now())
        ).seconds < config.extensions.duck.cooldown.value:
            cooldowns[message.author.id] = datetime.datetime.now()
            asyncio.create_task(
                message.author.send(
                    f"I said to wait {config.extensions.duck.cooldown.value}"
                    + " seconds! Resetting timer..."
                )
            )
            return False

        weights = (
            config.extensions.duck.success_rate.value,
            100 - config.extensions.duck.success_rate.value,
        )

        # Check to see if random failure
        choice_ = random.choice(random.choices([True, False], weights=weights, k=1000))
        if not choice_:
            cooldowns[message.author.id] = datetime.datetime.now()
            quote = self.pick_quote()
            embed = auxiliary.prepare_deny_embed(message=quote)
            embed.set_footer(
                text=f"You missed. Try again in {config.extensions.duck.cooldown.value} seconds"
            )
            # Only attempt timeout if we know we can do it
            if (
                channel.guild.me.top_role > message.author.top_role
                and channel.guild.me.guild_permissions.moderate_members
            ):
                asyncio.create_task(
                    message.author.timeout(
                        timedelta(seconds=config.extensions.duck.cooldown.value),
                        reason="Missed a duck",
                    )
                )
            asyncio.create_task(
                message.channel.send(
                    content=message.author.mention,
                    embed=embed,
                )
            )

        return choice_

    async def get_duck_user(
        self: Self, user_id: int, guild_id: int
    ) -> bot.models.DuckUser | None:
        """If it exists, will return the duck winner database entry

        Args:
            self (Self): _description_
            user_id (int): The integer ID of the user
            guild_id (int): The guild ID of where the user belongs to

        Returns:
            bot.models.DuckUser | None: The DuckUser database entry of the user/guild combo.
                Or None if it doesn't exist
        """
        duck_user = (
            await self.bot.models.DuckUser.query.where(
                self.bot.models.DuckUser.author_id == str(user_id)
            )
            .where(self.bot.models.DuckUser.guild_id == str(guild_id))
            .gino.first()
        )

        return duck_user

    async def get_global_record(self: Self, guild_id: int) -> float:
        """This is a function to get the current global speed record in a given guild

        Args:
            guild_id (int): The ID of the guild in question

        Returns:
            float: The exact decimal representation for the fastest speed record
        """

        query = await self.bot.models.DuckUser.query.where(
            self.bot.models.DuckUser.guild_id == str(guild_id)
        ).gino.all()

        speed_records = [record.speed_record for record in query]

        if not speed_records:
            return None

        return float(min(speed_records, key=float))

    @commands.group(
        brief="Executes a duck command",
        description="Executes a duck command",
    )
    async def duck(self: Self, ctx: commands.Context) -> None:
        """The bare .duck command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck stats",
        description="Gets duck friendships and kills for yourself or another user",
        usage="@user (defaults to yourself)",
    )
    async def stats(
        self: Self, ctx: commands.Context, *, user: discord.Member = None
    ) -> None:
        """Discord command for getting duck stats for a given user

        Args:
            self (Self): _description_
            ctx (commands.Context): The context in which the command was run
            user (discord.Member, optional): The member to lookup stats for.
                Defaults to ctx.message.author.
        """
        if not user:
            user = ctx.message.author

        if user.bot:
            await auxiliary.send_deny_embed(
                message="If it looks like a duck, quacks like a duck, it's a duck!",
                channel=ctx.channel,
            )
            return

        duck_user = await self.get_duck_user(user.id, ctx.guild.id)
        if not duck_user:
            await auxiliary.send_deny_embed(
                message="That user has not partcipated in the duck hunt",
                channel=ctx.channel,
            )
            return

        embed = discord.Embed(title="Duck Stats", description=user.mention)
        embed.color = embed_colors.green()
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        footer_string = f"Speed record: {str(duck_user.speed_record)} seconds"
        if duck_user.speed_record == await self.get_global_record(ctx.guild.id):
            footer_string += "\nYou hold the current global record!"
        embed.set_footer(text=footer_string)
        embed.set_thumbnail(url=self.DUCK_PIC_URL)

        await ctx.send(embed=embed)

    @auxiliary.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck friendship scores",
        description="Gets duck friendship scores for all users",
    )
    async def friends(self: Self, ctx: commands.Context) -> None:
        """Discord commands to view high scores for befriended ducks

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        duck_users = (
            await self.bot.models.DuckUser.query.order_by(
                -self.bot.models.DuckUser.befriend_count
            )
            .where(self.bot.models.DuckUser.befriend_count > 0)
            .where(self.bot.models.DuckUser.guild_id == str(ctx.guild.id))
            .gino.all()
        )

        if not duck_users:
            await auxiliary.send_deny_embed(
                message="It appears nobody has befriended any ducks",
                channel=ctx.channel,
            )
            return

        field_counter = 1
        embeds = []
        for index, duck_user in enumerate(duck_users):
            embed = (
                discord.Embed(
                    title="Duck Friendships",
                    description=(
                        "Global speed record: "
                        f" {str(await self.get_global_record(ctx.guild.id))} seconds"
                    ),
                )
                if field_counter == 1
                else embed
            )

            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()

            embed.add_field(
                name=self.get_user_text(duck_user),
                value=f"Friends: `{duck_user.befriend_count}`",
                inline=False,
            )
            if field_counter == 3 or index == len(duck_users) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)

    @auxiliary.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get the record holder",
        description="Gets the current speed record holder, and their time",
    )
    async def record(self: Self, ctx: commands.Context) -> None:
        """This outputs an embed shows the current speed record holder and their time
        This is a command and should be run via discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """

        record_time = await self.get_global_record(ctx.guild.id)
        if record_time is None:
            await auxiliary.send_deny_embed(
                message="It appears nobody has partcipated in the duck hunt",
                channel=ctx.channel,
            )
            return
        record_user = (
            await self.bot.models.DuckUser.query.where(
                self.bot.models.DuckUser.speed_record == record_time
            )
            .where(self.bot.models.DuckUser.guild_id == str(ctx.guild.id))
            .gino.first()
        )

        embed = discord.Embed(title="Duck Speed Record")
        embed.color = embed_colors.green()
        embed.add_field(name="Time", value=f"{str(record_time)} seconds")
        embed.add_field(name="Record Holder", value=f"<@{record_user.author_id}>")
        embed.set_thumbnail(url=self.DUCK_PIC_URL)

        await ctx.send(embed=embed)

    @auxiliary.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Get duck kill scores",
        description="Gets duck kill scores for all users",
    )
    async def killers(self: Self, ctx: commands.Context) -> None:
        """Discord command to view high scores for killed ducks

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        duck_users = (
            await self.bot.models.DuckUser.query.order_by(
                -self.bot.models.DuckUser.kill_count
            )
            .where(self.bot.models.DuckUser.kill_count > 0)
            .where(self.bot.models.DuckUser.guild_id == str(ctx.guild.id))
            .gino.all()
        )

        if not duck_users:
            await auxiliary.send_deny_embed(
                message="It appears nobody has killed any ducks", channel=ctx.channel
            )
            return

        field_counter = 1
        embeds = []
        for index, duck_user in enumerate(duck_users):
            embed = (
                discord.Embed(
                    title="Duck Kills",
                    description=(
                        "Global speed record: "
                        f" {str(await self.get_global_record(ctx.guild.id))} seconds"
                    ),
                )
                if field_counter == 1
                else embed
            )

            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()

            embed.add_field(
                name=self.get_user_text(duck_user),
                value=f"Kills: `{duck_user.kill_count}`",
                inline=False,
            )
            if field_counter == 3 or index == len(duck_users) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)

    def get_user_text(self: Self, duck_user: bot.models.DuckUser) -> str:
        """Gets the name of a user formatted to be displayed across the extension

        Args:
            duck_user (bot.models.DuckUser): The database entry of the user to format

        Returns:
            str: The username in a pretty string format, ready to print
        """
        user = self.bot.get_user(int(duck_user.author_id))
        if user:
            user_text = f"{user.display_name}"
            user_text_extra = f"({user.name})" if user.name != user.display_name else ""
        else:
            user_text = "<Unknown>"
            user_text_extra = ""
        return f"{user_text}{user_text_extra}"

    @auxiliary.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Releases a duck into the wild",
        description="Returns a befriended duck to its natural habitat",
    )
    async def release(self: Self, ctx: commands.Context) -> None:
        """Releases a duck into the wild, a duck will spawn in the channel this command is run from
        This is a discord command

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        config = self.bot.guild_configs[str(ctx.guild.id)]
        if not config.extensions.duck.allow_manipulation.value:
            await auxiliary.send_deny_embed(
                channel=ctx.channel, message="This command is disabled in this server"
            )
            return

        duck_user = await self.get_duck_user(ctx.author.id, ctx.guild.id)

        if not duck_user:
            await auxiliary.send_deny_embed(
                message="You have not participated in the duck hunt yet.",
                channel=ctx.channel,
            )
            return

        if not duck_user or duck_user.befriend_count == 0:
            await auxiliary.send_deny_embed(
                message="You have no ducks to release.", channel=ctx.channel
            )
            return

        await duck_user.update(befriend_count=duck_user.befriend_count - 1).apply()
        await auxiliary.send_confirm_embed(
            message=f"Fly safe! You have {duck_user.befriend_count} ducks left.",
            channel=ctx.channel,
        )

        await self.execute(config, ctx.guild, ctx.channel, banned_user=ctx.author)

    @auxiliary.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Kills a caputred duck",
        description=(
            "Adds a duck to your kill count. Why would you even want to do that?!"
        ),
    )
    async def kill(self: Self, ctx: commands.Context) -> None:
        """Kills a friended duck and adds it to your kills.
        Has a chance of failure
        This is a discord command

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        config = self.bot.guild_configs[str(ctx.guild.id)]
        if not config.extensions.duck.allow_manipulation.value:
            await auxiliary.send_deny_embed(
                channel=ctx.channel, message="This command is disabled in this server"
            )
            return

        duck_user = await self.get_duck_user(ctx.author.id, ctx.guild.id)

        if not duck_user:
            await auxiliary.send_deny_embed(
                message="You have not participated in the duck hunt yet.",
                channel=ctx.channel,
            )
            return

        if duck_user.befriend_count == 0:
            await auxiliary.send_deny_embed(
                message="You have no ducks to kill.", channel=ctx.channel
            )
            return

        await duck_user.update(befriend_count=duck_user.befriend_count - 1).apply()

        weights = (
            config.extensions.duck.success_rate.value,
            100 - config.extensions.duck.success_rate.value,
        )

        passed = random.choice(random.choices([True, False], weights=weights, k=1000))
        if not passed:
            await auxiliary.send_deny_embed(
                message="The duck got away before you could kill it.",
                channel=ctx.channel,
            )
            return

        await duck_user.update(kill_count=duck_user.kill_count + 1).apply()
        await auxiliary.send_confirm_embed(
            message=f"You monster! You have {duck_user.befriend_count} ducks "
            + f"left and {duck_user.kill_count} kills to your name.",
            channel=ctx.channel,
        )

    @auxiliary.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Donates a duck to someone",
        description="Gives someone the gift of a live duck",
        usage="[user]",
    )
    async def donate(self: Self, ctx: commands.Context, user: discord.Member) -> None:
        """Donates a befriended duck to a given user. Duck count will be subtracted from invoker
        This has a chance of failure
        This is a discord command

        Args:
            self (Self): _description_
            ctx (commands.Context): The context in which the command was run
            user (discord.Member): The user to donate a duck to
        """
        config = self.bot.guild_configs[str(ctx.guild.id)]
        if not config.extensions.duck.allow_manipulation.value:
            await auxiliary.send_deny_embed(
                channel=ctx.channel, message="This command is disabled in this server"
            )
            return

        if user.bot:
            await auxiliary.send_deny_embed(
                message="The only ducks I accept are plated with gold!",
                channel=ctx.channel,
            )
            return
        if user.id == ctx.author.id:
            await auxiliary.send_deny_embed(
                message="You can't donate a duck to yourself", channel=ctx.channel
            )
            return

        duck_user = await self.get_duck_user(ctx.author.id, ctx.guild.id)
        if not duck_user:
            await auxiliary.send_deny_embed(
                message="You have not participated in the duck hunt yet.",
                channel=ctx.channel,
            )
            return

        if not duck_user or duck_user.befriend_count == 0:
            await auxiliary.send_deny_embed(
                message="You have no ducks to donate.", channel=ctx.channel
            )
            return
        recipee = await self.get_duck_user(user.id, ctx.guild.id)
        if not recipee:
            await auxiliary.send_deny_embed(
                message=f"{user.mention} has not participated in the duck hunt yet.",
                channel=ctx.channel,
            )
            return

        await duck_user.update(befriend_count=duck_user.befriend_count - 1).apply()

        weights = (
            config.extensions.duck.success_rate.value,
            100 - config.extensions.duck.success_rate.value,
        )

        passed = random.choice(random.choices([True, False], weights=weights, k=1000))
        if not passed:
            await auxiliary.send_deny_embed(
                message="The duck got away before you could donate it.",
                channel=ctx.channel,
            )
            return

        await recipee.update(befriend_count=recipee.befriend_count + 1).apply()
        await auxiliary.send_confirm_embed(
            message=f"You gave a duck to {user.mention}. You now "
            + f"have {duck_user.befriend_count} ducks left.",
            channel=ctx.channel,
        )

    @auxiliary.with_typing
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @duck.command(
        brief="Resets someones duck counts",
        description="Deletes the database entry of the target",
        usage="[user]",
    )
    async def reset(self: Self, ctx: commands.Context, user: discord.Member) -> None:
        """Admin only command to delete a database entry of a given user
        This is a discord command

        Args:
            self (Self): _description_
            ctx (commands.Context): The context in which the command was run
            user (discord.Member): The user to reset
        """
        if user.bot:
            await auxiliary.send_deny_embed(
                message="You leave my ducks alone!", channel=ctx.channel
            )
            return

        duck_user = await self.get_duck_user(user.id, ctx.guild.id)
        if not duck_user:
            await auxiliary.send_deny_embed(
                message="The user has not participated in the duck hunt yet.",
                channel=ctx.channel,
            )
            return

        view = ui.Confirm()
        await view.send(
            message=f"Are you sure you want to reset {user.mention}s duck stats?",
            channel=ctx.channel,
            author=ctx.author,
        )
        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                message=f"{user.mention}s duck stats were NOT reset.",
                channel=ctx.channel,
            )
            return

        await duck_user.delete()
        await auxiliary.send_confirm_embed(
            message=f"Successfully reset {user.mention}s duck stats!",
            channel=ctx.channel,
        )

    @auxiliary.with_typing
    @commands.guild_only()
    @duck.command(
        brief="Spawns a duck on command",
        description="Will spawn a duck with the command",
    )
    async def spawn(self, ctx: commands.Context) -> None:
        """A debug focused command to force spawn a duck in any channel

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        config = self.bot.guild_configs[str(ctx.guild.id)]
        spawn_user = config.extensions.duck.spawn_user.value
        for person in spawn_user:
            if ctx.author.id == int(person):
                await self.execute(config, ctx.guild, ctx.channel)
                return
        await auxiliary.send_deny_embed(
            message="It looks like you don't have permissions to spawn a duck",
            channel=ctx.channel,
        )
