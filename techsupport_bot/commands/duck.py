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
from core import auxiliary, cogs, extensionconfig, moderation
from discord import Color as embed_colors
from discord import app_commands

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
        key="use_category",
        datatype="bool",
        title="Whether to use the whole category for ducks",
        description="Whether to use the whole category for ducks",
        default=False,
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
        key="mute_for_cooldown",
        datatype="bool",
        title="Uses the timeout feature for cooldown",
        description="If enabled, users who miss will be timed out for the cooldown seconds",
        default=True,
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


def compute_duration_values(raw_duration: datetime.timedelta) -> tuple[int, float]:
    """Computes integer and exact duration values used by duck game output.

    Args:
        raw_duration (datetime.timedelta): The elapsed time since duck spawn

    Returns:
        tuple[int, float]: Whole-second duration and exact duration with microseconds
    """
    duration_seconds = raw_duration.seconds
    duration_exact = float(f"{raw_duration.seconds}.{raw_duration.microseconds}")
    return duration_seconds, duration_exact


def build_winner_footer(
    duration_exact: float, previous_personal: float, global_record: float | None
) -> tuple[str, bool]:
    """Builds winner embed footer text and speed-record update state.

    Args:
        duration_exact (float): The exact completion time for the winner
        previous_personal (float): The winner's previous personal best
        global_record (float | None): The current global best in the guild

    Returns:
        tuple[str, bool]: Footer text and whether personal record should be updated
    """
    if previous_personal == -1 or duration_exact < previous_personal:
        footer_text = f"New personal record: {duration_exact} seconds."
        if global_record is None or duration_exact < global_record:
            footer_text += "\nNew global record!"
            if global_record is not None:
                footer_text += f" Previous global record: {global_record} seconds"
        return footer_text, True

    return f"Exact time: {duration_exact} seconds.", False


def build_stats_footer(speed_record: float, global_record: float | None) -> str:
    """Builds footer text for /duck stats response.

    Args:
        speed_record (float): User speed record
        global_record (float | None): Guild global speed record

    Returns:
        str: The final footer text
    """
    footer_text = f"Speed record: {speed_record} seconds"
    if global_record is not None and speed_record == global_record:
        footer_text += "\nYou hold the current global record!"
    return footer_text


def chunk_duck_users(
    duck_users: list[object], items_per_page: int = 3
) -> list[list[object]]:
    """Chunks duck user records for paginated leaderboard embeds.

    Args:
        duck_users (list[object]): Ordered duck user records
        items_per_page (int, optional): Max rows per page. Defaults to 3.

    Returns:
        list[list[object]]: Chunked records in display order
    """
    chunks = []
    current_chunk = []

    for duck_user in duck_users:
        current_chunk.append(duck_user)
        if len(current_chunk) == items_per_page:
            chunks.append(current_chunk)
            current_chunk = []

    if len(current_chunk) > 0:
        chunks.append(current_chunk)

    return chunks


def build_not_participated_message() -> str:
    """Builds the default message for users without duck records.

    Returns:
        str: A user-facing deny message
    """
    return "You have not participated in the duck hunt yet."


def build_manipulation_disabled_message() -> str:
    """Builds the message for manipulation-disabled servers.

    Returns:
        str: A user-facing deny message
    """
    return "This command is disabled in this server"


def validate_donation_target(
    invoker_id: int, target_id: int, target_is_bot: bool
) -> str | None:
    """Validates the target for duck donation commands.

    Args:
        invoker_id (int): The invoking user ID
        target_id (int): The donation target user ID
        target_is_bot (bool): Whether the target user is a bot

    Returns:
        str | None: A deny message when invalid, otherwise None
    """
    if target_is_bot:
        return "The only ducks I accept are plated with gold!"

    if invoker_id == target_id:
        return "You can't donate a duck to yourself"

    return None


def validate_duck_inventory(befriend_count: int, action_name: str) -> str | None:
    """Validates inventory for duck manipulation actions.

    Args:
        befriend_count (int): Current number of befriended ducks
        action_name (str): Action verb used in user-facing text

    Returns:
        str | None: A deny message when inventory is insufficient, otherwise None
    """
    if befriend_count > 0:
        return None

    return f"You have no ducks to {action_name}."


def can_spawn_duck(invoker_id: int, allowed_ids: list[int]) -> bool:
    """Determines if a user is allowed to spawn a duck.

    Args:
        invoker_id (int): The invoking user ID
        allowed_ids (list[int]): Configured user IDs allowed to spawn ducks

    Returns:
        bool: True if invoker may spawn a duck, otherwise False
    """
    normalized_ids = {int(user_id) for user_id in allowed_ids}
    return invoker_id in normalized_ids


def build_spawn_permission_denial() -> str:
    """Builds spawn permission deny message.

    Returns:
        str: A user-facing deny message
    """
    return "It looks like you don't have permissions to spawn a duck"


def build_random_choice_weights(success_rate: int) -> tuple[int, int]:
    """Builds weighted success and failure values for duck chance checks.

    Args:
        success_rate (int): Percent chance for success

    Returns:
        tuple[int, int]: Success and failure weights
    """
    return success_rate, 100 - success_rate


class DuckHunt(cogs.LoopCog):
    """Class for the actual duck commands

    Attributes:
        DUCK_PIC_URL (str): The picture for the duck
        BEFRIEND_URL (str): The picture for the befriend target
        KILL_URL (str): The picture for the kill target
        ON_START (bool): ???
        CHANNELS_KEY (str): The config item for the channels that the duck hunt should run
        duck_group (app_commands.Group): The group for the /duck commands
    """

    DUCK_PIC_URL: str = (
        "https://www.iconarchive.com/download/i107380/google/"
        + "noto-emoji-animals-nature/22276-duck.512.png"
    )
    BEFRIEND_URL: str = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/"
        + "f/fb/Noto_Emoji_v2.034_2665.svg/512px-Noto_Emoji_v2.034_2665.svg.png"
    )
    KILL_URL: str = (
        "https://www.iconarchive.com/download/i97188/iconsmind/outline/Target.512.png"
    )
    ON_START: bool = False
    CHANNELS_KEY: str = "hunt_channels"

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
        channel: discord.TextChannel,
        banned_user: discord.User = None,
    ) -> None:
        """Sends a duck in the given channel
        Can be manually called, and will be called automatically after wait()

        Args:
            config (munch.Munch): The config of the guild where the duck is going
            guild (discord.Guild): The guild where the duck is going
            channel (discord.TextChannel): The channel to spawn the duck in
            banned_user (discord.User, optional): A user that is not allowed to claim the duck.
                Defaults to None.
        """
        if not channel:
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message="Channel not found for Duckhunt loop - continuing",
                level=LogLevel.WARNING,
                context=LogContext(guild=guild),
                channel=log_channel,
            )
            return

        if config.extensions.duck.use_category.value:
            all_valid_channels = channel.category.text_channels
            use_channel = random.choice(all_valid_channels)
        else:
            use_channel = channel

        self.cooldowns[guild.id] = {}

        embed = discord.Embed(
            title="*Quack Quack*",
            description="Befriend the duck with `bef` or shoot with `bang`",
        )
        embed.set_image(url=self.DUCK_PIC_URL)
        embed.color = discord.Color.green()

        duck_message = await use_channel.send(embed=embed)
        start_time = duck_message.created_at

        response_message = None
        try:
            response_message = await self.bot.wait_for(
                "message",
                timeout=config.extensions.duck.timeout.value,
                # can't pull the config in a non-coroutine
                check=functools.partial(
                    self.message_check, config, use_channel, duck_message, banned_user
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
                context=LogContext(guild=guild, channel=use_channel),
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
                response_message.author, guild, action, raw_duration, use_channel
            )
        else:
            await self.got_away(use_channel)

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
        self: Self,
        winner: discord.Member,
        guild: discord.Guild,
        action: str,
        raw_duration: datetime.timedelta,
        channel: discord.abc.Messageable,
    ) -> None:
        """This is a function to update the database based on a winner

        Args:
            winner (discord.Member): A discord.Member object for the winner
            guild (discord.Guild): A discord.Guild object for the guild the winner is a part of
            action (str): A string, either "befriended" or "killed", depending on the action
            raw_duration (datetime.timedelta): Time elapsed since duck spawn
            channel (discord.abc.Messageable): The channel in which the duck game happened in
        """

        config_ = self.bot.guild_configs[str(guild.id)]
        log_channel = config_.get("logging_channel")
        await self.bot.logger.send_log(
            message=f"Duck {action} by {winner} in #{channel.name}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild, channel=channel),
            channel=log_channel,
        )

        duration_seconds, duration_exact = compute_duration_values(raw_duration)

        duck_user = await self.get_duck_user(winner.id, guild.id)
        if not duck_user:
            duck_user = self.bot.models.DuckUser(
                author_id=str(winner.id),
                guild_id=str(guild.id),
                befriend_count=0,
                kill_count=0,
                speed_record=-1.0,
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
        footer_string, should_update_personal = build_winner_footer(
            duration_exact=duration_exact,
            previous_personal=duck_user.speed_record,
            global_record=global_record,
        )
        if should_update_personal:
            await duck_user.update(speed_record=duration_exact).apply()
        embed.set_footer(text=footer_string)

        await channel.send(embed=embed)

    def pick_quote(self: Self) -> str:
        """Picks a random quote from the duckQuotes.txt file

        Returns:
            str: The quote picked randomly from the file, ready to use"""
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

        # Check to see if random failure
        choice = self.random_choice(config)
        if not choice:
            time = message.created_at - duck_message.created_at
            duration_exact = float(str(time.seconds) + "." + str(time.microseconds))
            cooldowns[message.author.id] = datetime.datetime.now()
            quote = self.pick_quote()
            embed = auxiliary.prepare_deny_embed(message=quote)
            embed.set_footer(
                text=(
                    f"You missed. Try again in {config.extensions.duck.cooldown.value} "
                    f"seconds. Time would have been {duration_exact} seconds"
                )
            )

            if (
                config.extensions.duck.mute_for_cooldown.value
                and config.extensions.duck.cooldown.value > 0
            ):
                # Only attempt timeout if we know we can do it
                if (
                    channel.guild.me.top_role > message.author.top_role
                    and channel.guild.me.guild_permissions.moderate_members
                ):
                    asyncio.create_task(
                        moderation.mute_user(
                            user=message.author,
                            reason="Missed a duck",
                            duration=timedelta(
                                seconds=config.extensions.duck.cooldown.value
                            ),
                        )
                    )

            asyncio.create_task(
                message.channel.send(
                    content=message.author.mention,
                    embed=embed,
                )
            )

        return choice

    async def get_duck_user(
        self: Self, user_id: int, guild_id: int
    ) -> bot.models.DuckUser | None:
        """If it exists, will return the duck winner database entry

        Args:
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

        speed_records = [
            record.speed_record for record in query if record.speed_record != -1
        ]

        if not speed_records:
            return None

        return float(min(speed_records, key=float))

    duck_group: app_commands.Group = app_commands.Group(
        name="duck",
        description="Command Group for Duck Hunt",
        extras={"module": "duck"},
    )

    @duck_group.command(
        name="stats",
        description="Gets duck friendships and kills for yourself or another user",
        extras={"module": "duck"},
    )
    async def stats(
        self: Self, interaction: discord.Interaction, user: discord.Member = None
    ) -> None:
        """Gets duck stats for a given user.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
            user (discord.Member, optional): The member to lookup stats for.
                Defaults to the invoking user.
        """
        await interaction.response.defer(ephemeral=False)
        if not user:
            user = interaction.user

        if user.bot:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "If it looks like a duck, quacks like a duck, it's a duck!"
                ),
                ephemeral=True,
            )
            return

        duck_user = await self.get_duck_user(user.id, interaction.guild.id)
        if not duck_user:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "That user has not partcipated in the duck hunt"
                ),
                ephemeral=True,
            )
            return

        global_record = await self.get_global_record(interaction.guild.id)
        embed = discord.Embed(title="Duck Stats", description=user.mention)
        embed.color = embed_colors.green()
        embed.add_field(name="Friends", value=duck_user.befriend_count)
        embed.add_field(name="Kills", value=duck_user.kill_count)
        embed.set_footer(text=build_stats_footer(duck_user.speed_record, global_record))
        embed.set_thumbnail(url=self.DUCK_PIC_URL)

        await interaction.followup.send(embed=embed)

    @duck_group.command(
        name="friends",
        description="Gets duck friendship scores for all users",
        extras={"module": "duck"},
    )
    async def friends(self: Self, interaction: discord.Interaction) -> None:
        """Views high scores for befriended ducks.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
        """
        await interaction.response.defer(ephemeral=False)
        duck_users = (
            await self.bot.models.DuckUser.query.order_by(
                -self.bot.models.DuckUser.befriend_count
            )
            .where(self.bot.models.DuckUser.befriend_count > 0)
            .where(self.bot.models.DuckUser.guild_id == str(interaction.guild.id))
            .gino.all()
        )

        if not duck_users:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "It appears nobody has befriended any ducks"
                ),
                ephemeral=True,
            )
            return

        global_record = await self.get_global_record(interaction.guild.id)
        embeds = []
        for chunk in chunk_duck_users(duck_users):
            embed = discord.Embed(
                title="Duck Friendships",
                description=f"Global speed record: {global_record} seconds",
            )
            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()
            for duck_user in chunk:
                embed.add_field(
                    name=await self.get_user_text(duck_user, interaction.guild),
                    value=f"Friends: `{duck_user.befriend_count}`",
                    inline=False,
                )
            embeds.append(embed)

        await ui.PaginateView().send(
            interaction.channel, interaction.user, embeds, interaction
        )

    @duck_group.command(
        name="record",
        description="Gets the current speed record holder and their time",
        extras={"module": "duck"},
    )
    async def record(self: Self, interaction: discord.Interaction) -> None:
        """Shows the current speed record holder and time.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
        """
        await interaction.response.defer(ephemeral=False)
        record_time = await self.get_global_record(interaction.guild.id)
        if record_time is None:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "It appears nobody has partcipated in the duck hunt"
                ),
                ephemeral=True,
            )
            return
        record_user_entry = (
            await self.bot.models.DuckUser.query.where(
                self.bot.models.DuckUser.speed_record == record_time
            )
            .where(self.bot.models.DuckUser.guild_id == str(interaction.guild.id))
            .gino.first()
        )
        embed = discord.Embed(title="Duck Speed Record")
        embed.color = embed_colors.green()
        embed.add_field(name="Time", value=f"{record_time} seconds")
        embed.add_field(
            name="Record Holder",
            value=await self.get_user_text(record_user_entry, interaction.guild),
        )
        embed.set_thumbnail(url=self.DUCK_PIC_URL)

        await interaction.followup.send(embed=embed)

    @duck_group.command(
        name="killers",
        description="Gets duck kill scores for all users",
        extras={"module": "duck"},
    )
    async def killers(self: Self, interaction: discord.Interaction) -> None:
        """Views high scores for killed ducks.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
        """
        await interaction.response.defer(ephemeral=False)
        duck_users = (
            await self.bot.models.DuckUser.query.order_by(
                -self.bot.models.DuckUser.kill_count
            )
            .where(self.bot.models.DuckUser.kill_count > 0)
            .where(self.bot.models.DuckUser.guild_id == str(interaction.guild.id))
            .gino.all()
        )

        if not duck_users:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "It appears nobody has killed any ducks"
                ),
                ephemeral=True,
            )
            return

        global_record = await self.get_global_record(interaction.guild.id)
        embeds = []
        for chunk in chunk_duck_users(duck_users):
            embed = discord.Embed(
                title="Duck Kills",
                description=f"Global speed record: {global_record} seconds",
            )
            embed.set_thumbnail(url=self.DUCK_PIC_URL)
            embed.color = embed_colors.green()
            for duck_user in chunk:
                embed.add_field(
                    name=await self.get_user_text(duck_user, interaction.guild),
                    value=f"Kills: `{duck_user.kill_count}`",
                    inline=False,
                )
            embeds.append(embed)

        await ui.PaginateView().send(
            interaction.channel, interaction.user, embeds, interaction
        )

    async def get_user_text(
        self: Self, duck_user: bot.models.DuckUser, guild: discord.Guild
    ) -> str:
        """Gets the name of a user formatted to be displayed across the extension

        Args:
            duck_user (bot.models.DuckUser): The database entry of the user to format
            guild (discord.Guild): The guild to fetch duck records from

        Returns:
            str: The username in a pretty string format, ready to print
        """
        try:
            user_object = await self.bot.fetch_user(duck_user.author_id)
        except discord.NotFound:
            return f"`Account not found` ({duck_user.author_id})"
        display_name = user_object.global_name
        try:
            member_object = await guild.fetch_member(user_object.id)
            display_name = member_object.display_name
        except discord.NotFound:
            ...

        return f"`{display_name}` (`{user_object.name}`)"

    @duck_group.command(
        name="release",
        description="Returns a befriended duck to its natural habitat",
        extras={"module": "duck"},
    )
    async def release(self: Self, interaction: discord.Interaction) -> None:
        """Releases a duck into the wild and spawns one in-channel.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
        """
        await interaction.response.defer(ephemeral=False)
        config = self.bot.guild_configs[str(interaction.guild.id)]
        if not config.extensions.duck.allow_manipulation.value:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    build_manipulation_disabled_message()
                ),
                ephemeral=True,
            )
            return

        duck_user = await self.get_duck_user(interaction.user.id, interaction.guild.id)
        if not duck_user:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(build_not_participated_message()),
                ephemeral=True,
            )
            return

        missing_inventory = validate_duck_inventory(duck_user.befriend_count, "release")
        if missing_inventory:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(missing_inventory),
                ephemeral=True,
            )
            return

        await duck_user.update(befriend_count=duck_user.befriend_count - 1).apply()
        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed(
                f"Fly safe! You have {duck_user.befriend_count} ducks left."
            )
        )

        await self.execute(
            config, interaction.guild, interaction.channel, interaction.user
        )

    @duck_group.command(
        name="kill",
        description="Adds a duck to your kill count",
        extras={"module": "duck"},
    )
    async def kill(self: Self, interaction: discord.Interaction) -> None:
        """Kills a befriended duck and adds it to your kills.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
        """
        await interaction.response.defer(ephemeral=False)
        config = self.bot.guild_configs[str(interaction.guild.id)]
        if not config.extensions.duck.allow_manipulation.value:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    build_manipulation_disabled_message()
                ),
                ephemeral=True,
            )
            return

        duck_user = await self.get_duck_user(interaction.user.id, interaction.guild.id)
        if not duck_user:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(build_not_participated_message()),
                ephemeral=True,
            )
            return

        missing_inventory = validate_duck_inventory(duck_user.befriend_count, "kill")
        if missing_inventory:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(missing_inventory),
                ephemeral=True,
            )
            return

        await duck_user.update(befriend_count=duck_user.befriend_count - 1).apply()
        if not self.random_choice(config):
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "The duck got away before you could kill it."
                ),
                ephemeral=True,
            )
            return

        await duck_user.update(kill_count=duck_user.kill_count + 1).apply()
        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed(
                f"You monster! You have {duck_user.befriend_count} ducks left and "
                f"{duck_user.kill_count} kills to your name."
            )
        )

    @duck_group.command(
        name="donate",
        description="Gives someone the gift of a live duck",
        extras={"module": "duck"},
    )
    async def donate(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Donates a befriended duck to a given user.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
            user (discord.Member): The user to donate a duck to
        """
        await interaction.response.defer(ephemeral=False)
        config = self.bot.guild_configs[str(interaction.guild.id)]
        if not config.extensions.duck.allow_manipulation.value:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    build_manipulation_disabled_message()
                ),
                ephemeral=True,
            )
            return

        target_invalid = validate_donation_target(
            interaction.user.id, user.id, user.bot
        )
        if target_invalid:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(target_invalid), ephemeral=True
            )
            return

        duck_user = await self.get_duck_user(interaction.user.id, interaction.guild.id)
        if not duck_user:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(build_not_participated_message()),
                ephemeral=True,
            )
            return

        missing_inventory = validate_duck_inventory(duck_user.befriend_count, "donate")
        if missing_inventory:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(missing_inventory),
                ephemeral=True,
            )
            return

        recipient = await self.get_duck_user(user.id, interaction.guild.id)
        if not recipient:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    f"{user.mention} has not participated in the duck hunt yet."
                ),
                ephemeral=True,
            )
            return

        await duck_user.update(befriend_count=duck_user.befriend_count - 1).apply()
        if not self.random_choice(config):
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "The duck got away before you could donate it."
                ),
                ephemeral=True,
            )
            return

        await recipient.update(befriend_count=recipient.befriend_count + 1).apply()
        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed(
                f"You gave a duck to {user.mention}. You now have"
                f" {duck_user.befriend_count} ducks left."
            )
        )

    @app_commands.checks.has_permissions(administrator=True)
    @duck_group.command(
        name="reset",
        description="Deletes the duck database entry of the target",
        extras={"module": "duck"},
    )
    async def reset(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Admin command to delete duck stats for a user.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
            user (discord.Member): The user to reset
        """
        await interaction.response.defer(ephemeral=False)
        if user.bot:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed("You leave my ducks alone!"),
                ephemeral=True,
            )
            return

        duck_user = await self.get_duck_user(user.id, interaction.guild.id)
        if not duck_user:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    "The user has not participated in the duck hunt yet."
                ),
                ephemeral=True,
            )
            return

        view = ui.Confirm()
        await view.send(
            message=f"Are you sure you want to reset {user.mention}s duck stats?",
            channel=interaction.channel,
            author=interaction.user,
            interaction=interaction,
        )
        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(
                    f"{user.mention}s duck stats were NOT reset."
                ),
                ephemeral=True,
            )
            return

        await duck_user.delete()
        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed(
                f"Successfully reset {user.mention}s duck stats!"
            )
        )

    @duck_group.command(
        name="spawn",
        description="Spawns a duck on command",
        extras={"module": "duck"},
    )
    async def spawn(self: Self, interaction: discord.Interaction) -> None:
        """Force spawns a duck in current channel if allowed by config.

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
        """
        await interaction.response.defer(ephemeral=False)
        config = self.bot.guild_configs[str(interaction.guild.id)]
        spawn_user = config.extensions.duck.spawn_user.value

        if not can_spawn_duck(interaction.user.id, spawn_user):
            await interaction.followup.send(
                embed=auxiliary.prepare_deny_embed(build_spawn_permission_denial()),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed("Duck spawned successfully."),
            ephemeral=True,
        )
        asyncio.create_task(
            self.execute(config, interaction.guild, interaction.channel)
        )

    def random_choice(self: Self, config: munch.Munch) -> bool:
        """Picks true/false randomly based on configured success rate.

        Args:
            config (munch.Munch): The config for the guild

        Returns:
            bool: Whether the random choice should succeed or not
        """
        weights = build_random_choice_weights(config.extensions.duck.success_rate.value)
        choice_ = random.choice(
            random.choices([True, False], weights=weights, k=100000)
        )
        return choice_
