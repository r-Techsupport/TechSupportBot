"""Basic modmail client setup and staff-initiated thread creation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, NamedTuple, Self

import discord
from discord import app_commands

import configuration
from core import auxiliary, cogs
from modules.moderation import featureban

if TYPE_CHECKING:
    import bot


class ModmailThreadName(NamedTuple):
    """The fields parsed from a modmail thread name.

    Attributes:
        open (bool): True for [OPEN] threads, False for [CLOSED] threads
        username (str): The username recorded in the thread name
        opened_at (datetime): The opening date and time, without timezone information
        user_id (int): The Discord user ID recorded in the thread name
    """

    open: bool
    username: str
    opened_at: datetime
    user_id: int


def parse_modmail_thread_name(name: str) -> ModmailThreadName | None:
    """Parse a modmail thread name, returning None for noncompliant names.

    Args:
        name (str): The thread name to parse

    Returns:
        ModmailThreadName | None: The parsed fields, or None if invalid
    """
    parts = [part.strip() for part in name.split("|")]
    if len(parts) != 4:
        return None
    status, username, opened_at, user_id = parts
    if status not in ("[OPEN]", "[CLOSED]") or not username:
        return None
    if not user_id.isascii() or not user_id.isdecimal():
        return None
    try:
        opened_date = datetime.strptime(opened_at, "%Y-%m-%d %H:%M:%S")
        parsed_user_id = int(user_id)
    except ValueError:
        return None
    return ModmailThreadName(status == "[OPEN]", username, opened_date, parsed_user_id)


async def has_modmail_management_role(interaction: discord.Interaction) -> bool:
    """Require one of the configured modmail roles.

    Args:
        interaction (discord.Interaction): The command interaction

    Raises:
        AppCommandError: No modmail roles are configured
        MissingAnyRole: The caller has none of the configured roles

    Returns:
        bool: Whether the caller may manage modmail
    """
    role_ids = configuration.get_config_entry(
        interaction.guild_id, "modmail_modmail_roles"
    )
    if not role_ids:
        raise app_commands.AppCommandError("No modmail management roles are configured")
    roles = [int(role_id) for role_id in role_ids]
    if not any(role.id in roles for role in interaction.user.roles):
        raise app_commands.MissingAnyRole(roles)
    return True


class Modmail_bot(discord.Client):
    """The modmail bot instance, this won't do much but handle DMs to/from users

    Args:
        ts_bot (bot.TechSupportBot): The core bot handling guild operations
        modmail_cog (Modmail): The modmail cog on TS

    Attributes:
        modmail_guild (discord.Guild | None): The current configured guild from TS
    """

    def __init__(
        self: Self,
        ts_bot: bot.TechSupportBot,
        modmail_cog: Modmail,
    ) -> None:
        # Setup default intents and call the discord.Client init call to start the bot
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.ts_bot = ts_bot
        self.modmail_cog = modmail_cog

    async def on_message(self: Self, message: discord.Message) -> None:
        """Open a modmail thread when a user sends this bot a DM.

        Args:
            message (discord.Message): The received message
        """
        if not isinstance(message.channel, discord.DMChannel) or message.author.bot:
            return

        await self.ts_bot.wait_until_ready()
        guild = self.modmail_cog.modmail_guild
        if guild is None:
            await message.channel.send(
                embed=auxiliary.prepare_deny_embed(
                    "The configured modmail guild is not available to TS."
                )
            )
            return
        if self.modmail_cog.is_thread_creation_disabled():
            await message.channel.send(
                embed=auxiliary.prepare_deny_embed(
                    "Modmail thread creation is disabled."
                )
            )
            return

        member = guild.get_member(message.author.id)
        if member is None:
            try:
                member = await guild.fetch_member(message.author.id)
            except discord.NotFound:
                await message.channel.send(
                    embed=auxiliary.prepare_deny_embed(
                        "You must be in the modmail guild to open a thread."
                    )
                )
                return

        try:
            await self.modmail_cog.create_thread(member)
        except PermissionError:
            embed = auxiliary.prepare_deny_embed("You are banned from modmail.")
        except ValueError:
            embed = auxiliary.prepare_deny_embed(
                "You already have an open modmail thread."
            )
        else:
            embed = auxiliary.prepare_confirm_embed(
                "Your modmail thread has been created."
            )
        await message.channel.send(embed=embed)

    async def on_typing(
        self: Self, channel: discord.DMChannel, user: discord.User, _: datetime
    ) -> None:
        """Reserve the DM typing handler.

        Args:
            channel (discord.DMChannel): The channel where typing started
            user (discord.User): The user typing
        """

    async def on_message_edit(
        self: Self, before: discord.Message, after: discord.Message
    ) -> None:
        """Reserve the DM edit handler.

        Args:
            before (discord.Message): The original message
            after (discord.Message): The updated message
        """

    async def on_message_delete(self: Self, message: discord.Message) -> None: ...


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Modmail plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if modmail is disabled
    """

    # Only runs if modmail is enabled
    if not bot.file_config.modmail_config.enable_modmail:
        raise AttributeError("Modmail was not loaded because it's disabled")

    # Don't run if there is no API key
    if not bot.file_config.modmail_config.modmail_auth_token:
        raise AttributeError("Modmail was not loaded because no auth token is provided")

    # Don't run if there is no guild
    if not bot.file_config.modmail_config.modmail_guild:
        raise AttributeError("Modmail was not loaded because no guild is provided")

    await bot.add_cog(Modmail(bot=bot))


class Modmail(cogs.BaseCog):
    """The TS modmail commands and startup hooks.

    Args:
        bot (bot.TechSupportBot): The core TS bot

    Attributes:
        modmail_commands (app_commands.Group): The modmail command group
        modmail_guild (discord.Guild | None): The current configured guild from TS
    """

    modmail_commands: app_commands.Group = app_commands.Group(
        name="modmail", description="The group of modmail commands", guild_only=True
    )

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        self.thread_creation_lock = asyncio.Lock()
        self.active_threads: dict[int, discord.Thread] = {}
        super().__init__(bot=bot)
        # Auth token rejection still needs handling.
        self.bot.modmail_client = Modmail_bot(ts_bot=self.bot, modmail_cog=self)
        self.modmail_task = self.bot.loop.create_task(
            self.bot.modmail_client.start(
                self.bot.file_config.modmail_config.modmail_auth_token
            )
        )

    @property
    def modmail_guild(self: Self) -> discord.Guild:
        """A dynamic fetching of the guild modmail is configured to run in, to ensure no cache misses break modmail

        Returns:
            discord.Guild: The configured guild if it is in TS's cache
        """
        return self.bot.get_guild(
            int(self.bot.file_config.modmail_config.modmail_guild)
        )

    # COMMANDS

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="contact", description="Creates a modmail thread with a user"
    )
    async def contact(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Create a staff-initiated thread without sending a DM.

        Args:
            interaction (discord.Interaction): The command interaction
            user (discord.Member): The member to create a thread for
        """
        await self.handle_contact(interaction, user)

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="selfcontact", description="Creates a modmail thread with yourself"
    )
    async def selfcontact(self: Self, interaction: discord.Interaction) -> None:
        """Create a thread for the invoking moderator.

        Args:
            interaction (discord.Interaction): The command interaction
        """
        await self.handle_contact(interaction, interaction.user)

    # LISTENERS

    @cogs.BaseCog.listener()
    async def on_member_join(self: Self, member: discord.Member) -> None:
        """Reserve the TS member join handler.

        Args:
            member (discord.Member): The member who joined
        """

    @cogs.BaseCog.listener()
    async def on_member_remove(self: Self, member: discord.Member) -> None:
        """Reserve the TS member leave handler.

        Args:
            member (discord.Member): The member who left
        """

    # HELPERS

    async def handle_contact(
        self: Self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Handle the shared contact and selfcontact creation flow.

        Args:
            interaction (discord.Interaction): The command interaction
            user (discord.Member): The member to create a thread for
        """
        if interaction.guild_id != int(
            self.bot.file_config.modmail_config.modmail_guild
        ):
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "This command is only available in the modmail guild."
                ),
                ephemeral=True,
            )
            return
        if self.is_thread_creation_disabled():
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "Modmail thread creation is disabled."
                ),
                ephemeral=True,
            )
            return
        if user.bot:
            await interaction.response.send_message(
                embed=auxiliary.prepare_deny_embed(
                    "You cannot open a modmail thread with a bot."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        try:
            thread = await self.create_thread(user)
        except (ValueError, PermissionError) as exc:
            embed = auxiliary.prepare_deny_embed(str(exc))
        else:
            embed = auxiliary.prepare_confirm_embed(f"Thread created: {thread.mention}")
        await interaction.followup.send(embed=embed)

    def is_thread_creation_disabled(self: Self) -> bool:
        """Read the configured thread creation switch.

        Returns:
            bool: Whether new modmail threads are disabled
        """
        return configuration.get_config_entry(
            int(self.modmail_guild.id),
            "modmail_disable_thread_creation",
        )

    async def get_forum(self: Self) -> discord.ForumChannel:
        """Resolve and validate the configured modmail forum through TS.

        Raises:
            ValueError: The guild is unavailable or the configured channel is not a forum

        Returns:
            discord.ForumChannel: The forum used for modmail threads
        """
        guild = self.modmail_guild
        if guild is None:
            raise ValueError("The configured modmail guild is not available to TS.")
        forum_id = int(
            configuration.get_config_entry(guild.id, "modmail_forum_channel")
        )
        forum = guild.get_channel(forum_id) or await guild.fetch_channel(forum_id)
        if not isinstance(forum, discord.ForumChannel):
            raise ValueError("The configured modmail channel must be a forum.")
        return forum

    async def is_banned(self: Self, user: discord.Member) -> bool:
        return await featureban.is_feature_banned(
                self.modmail_guild.id, user.id, featureban.FeatureFlag.MODMAIL
            )

    async def create_thread(
        self: Self,
        user: discord.Member,
    ) -> discord.Thread:
        """Check for an existing thread and create one under the same async lock.

        Args:
            forum (discord.ForumChannel): The configured TS modmail forum
            user (discord.Member): The person the thread is for

        Raises:
            PermissionError: The target user is banned from modmail
            ValueError: The user already has an open thread

        Returns:
            discord.Thread: The newly created thread
        """
        async with self.thread_creation_lock:
            try:
                forum = await self.get_forum()
            except ValueError as exc:
                raise ValueError(f"Forum channel could not be found: {exc}")
            if await self.is_banned(user):
                raise PermissionError("This user is banned from modmail.")
            existing = self.active_threads.get(user.id)
            # TODO: Improve this section
            # TODO: Allow different errors for contact and DM handling
            if existing is not None and not existing.name.startswith("[OPEN]"):
                self.active_threads.pop(user.id)
                existing = None
            if existing is None:
                for thread in forum.threads:
                    parsed_name = parse_modmail_thread_name(thread.name)
                    if parsed_name is None:
                        continue
                    if not parsed_name.open:
                        continue
                    if parsed_name.user_id != user.id:
                        continue
                    existing = thread
                    break
            if existing:
                self.active_threads[user.id] = existing
                raise ValueError(
                    f"An open thread for {user.mention} already exists: {existing.mention}"
                )

            past_threads = 0
            async for thread in forum.archived_threads():
                parsed_name = parse_modmail_thread_name(thread.name)
                if parsed_name is None or parsed_name.user_id != user.id:
                    continue
                if parsed_name.open:
                    self.active_threads[user.id] = thread
                    raise ValueError(
                        f"An open thread for {user.mention} already exists: {existing.mention}"
                    )
                past_threads += 1

            description = f"{user.mention} was created {discord.utils.format_dt(user.created_at, 'R')}"
            description += (
                f", has **{past_threads}** past threads"
                if past_threads
                else ", has **no** past threads"
            )
            if user.joined_at:
                description += (
                    f", joined {discord.utils.format_dt(user.joined_at, 'R')}"
                )
            embed = discord.Embed(description=description, color=discord.Color.blue())
            embed.add_field(name="Nickname", value=user.nick or "None")
            roles = [
                role.mention
                for role in sorted(
                    user.roles, key=lambda role: role.position, reverse=True
                )
                if not role.is_default()
            ]
            embed.add_field(name="Roles", value=", ".join(roles)[:1024] or "None")
            embed.set_author(name=str(user), icon_url=user.display_avatar.url)
            embed.set_footer(text=f"User ID: {user.id}")
            embed.timestamp = datetime.now(UTC)
            created = await forum.create_thread(
                name=f"[OPEN] | {user} | {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} | {user.id}",
                embed=embed,
            )
            self.active_threads[user.id] = created.thread
            return created.thread
