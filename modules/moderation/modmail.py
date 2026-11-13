# TODO: Handle attachments across the board
# TODO: Globally ignore any pinned threads

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, NamedTuple, Self

import discord
from bidict import bidict
from discord import app_commands

import configuration
from core import auxiliary, cogs
from modules.moderation import featureban

if TYPE_CHECKING:
    import bot


class ModmailThreadName(NamedTuple):
    """The fields parsed from a modmail thread name.

    Attributes:
        is_open (bool): True for [OPEN] threads, False for [CLOSED] threads
        username (str): The username recorded in the thread name
        opened_at (datetime): The opening date and time, without timezone information
        user_id (int): The Discord user ID recorded in the thread name
    """

    is_open: bool
    username: str
    opened_at: datetime
    user_id: int


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
    """The modmail bot instance, this won't do much but handle DMs to/from users.

    Args:
        ts_bot (bot.TechSupportBot): The core bot handling guild operations
        modmail_cog (Modmail): The modmail cog on TS
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
        """Pass incoming user DMs to the modmail cog.

        Args:
            message (discord.Message): The received message
        """
        if not isinstance(message.channel, discord.DMChannel) or message.author.bot:
            return

        await self.modmail_cog.handle_dm(message)

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
        """Forward user DM edits to their staff copies.

        Args:
            before (discord.Message): The original message
            after (discord.Message): The updated message
        """
        if (
            not isinstance(after.channel, discord.DMChannel)
            or after.author.bot
            or before.content == after.content
        ):
            return

        await self.modmail_cog.handle_dm_edit(after)

    async def on_message_delete(self: Self, message: discord.Message) -> None:
        """Mark the staff copy when a user deletes a forwarded DM.

        Args:
            message (discord.Message): The deleted DM
        """
        if not isinstance(message.channel, discord.DMChannel) or message.author.bot:
            return

        await self.modmail_cog.handle_dm_delete(message)


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
    """Starts the modmail bot, and holds all modmail functions and commands

    Args:
        bot (bot.TechSupportBot): The core TS bot

    Attributes:
        modmail_commands (app_commands.Group): The modmail command group
        modmail_guild (discord.Guild | None): The current configured guild from TS
        message_id_map (bidict[int, int]): DM message IDs mapped to TS staff message IDs
    """

    modmail_commands: app_commands.Group = app_commands.Group(
        name="modmail", description="The group of modmail commands", guild_only=True
    )

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        self.thread_creation_lock = asyncio.Lock()
        self.active_threads: dict[int, discord.Thread] = {}
        self.message_id_map: bidict[int, int] = bidict()
        super().__init__(bot=bot)
        # TODO: Auth token rejection still needs handling.
        self.bot.modmail_client = Modmail_bot(ts_bot=self.bot, modmail_cog=self)
        self.modmail_task = self.bot.loop.create_task(
            self.bot.modmail_client.start(
                self.bot.file_config.modmail_config.modmail_auth_token
            )
        )

    # COMMANDS

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="contact", description="Creates a modmail thread with a user"
    )
    async def contact(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        message: app_commands.Range[str, 1, 2000],
    ) -> None:
        """Create a staff-initiated thread and send its first message.

        Args:
            interaction (discord.Interaction): The command interaction
            user (discord.Member): The member to create a thread for
            message (app_commands.Range[str, 1, 2000]): The message to send to the member
        """
        await self.handle_contact(interaction, user, message)

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="reply", description="Reply to the current modmail conversation"
    )
    async def reply(
        self: Self,
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, 2000],
        deanonymize: bool = False,
    ) -> None:
        """Reply in an open modmail thread, anonymously unless requested otherwise.

        Args:
            interaction (discord.Interaction): The command interaction
            message (app_commands.Range[str, 1, 2000]): The reply text
            deanonymize (bool): Whether to show the sender's username to the recipient
        """
        if interaction.guild != self.modmail_guild or not isinstance(
            interaction.channel, discord.Thread
        ):
            await interaction.response.send_message(
                "This command can only be used in an open modmail thread.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)
        try:
            forum = await self.get_forum()
            thread = await forum.guild.fetch_channel(interaction.channel.id)
        except ValueError as exc:
            await interaction.edit_original_response(content=str(exc))
            return
        except discord.NotFound:
            await interaction.edit_original_response(
                content="The modmail thread could not be found."
            )
            return
        except discord.HTTPException:
            await interaction.edit_original_response(
                content="The modmail thread could not be fetched. Please try again later."
            )
            return

        if (
            not isinstance(thread, discord.Thread)
            or thread.parent_id != forum.id
            or not self.is_open_thread(thread)
        ):
            await interaction.edit_original_response(
                content="This command can only be used in an open modmail thread."
            )
            return

        parsed_name = self.parse_modmail_thread_name(thread.name)

        try:
            user = await self.get_modmail_member(parsed_name.user_id)
        except ValueError as exc:
            await interaction.edit_original_response(content=str(exc))
            return

        if user is None:
            await interaction.edit_original_response(
                content="The recipient is no longer in the modmail guild."
            )
            return

        timestamp = datetime.now(UTC)
        view = await self.build_staff_message_view(
            interaction.user,
            message,
            timestamp,
            user_id=user.id,
            anonymous=not deanonymize,
        )
        try:
            dm_message = await self.send_staff_dm(
                thread.guild,
                user,
                interaction.user,
                message,
                timestamp,
                anonymous=not deanonymize,
            )
        except ValueError as exc:
            await interaction.edit_original_response(content=str(exc))
            return
        except discord.NotFound:
            await interaction.edit_original_response(
                content="The DM recipient could not be found."
            )
            return
        except discord.HTTPException as exc:
            await interaction.edit_original_response(
                content=f"The reply could not be sent to the user. They probably have DMs off: {exc}"
            )
            return

        # We edit here to make the output on discord attributes to running the command properly
        try:
            staff_message = await interaction.edit_original_response(
                content=None, view=view
            )
        except discord.HTTPException as exc:
            await interaction.followup.send(
                f"The DM was delivered, but the staff copy could not be displayed: {exc}.",
                ephemeral=True,
            )
            return
        self.message_id_map[dm_message.id] = staff_message.id

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="selfcontact", description="Creates a modmail thread with yourself"
    )
    async def selfcontact(
        self: Self,
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, 2000],
    ) -> None:
        """Create a thread and send a message to the invoking moderator.

        Args:
            interaction (discord.Interaction): The command interaction
            message (app_commands.Range[str, 1, 2000]): The message to send to the invoking moderator
        """
        await self.handle_contact(interaction, interaction.user, message)

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

    # HELPERS - INFO GATHER

    def parse_modmail_thread_name(self: Self, name: str) -> ModmailThreadName | None:
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
        return ModmailThreadName(
            status == "[OPEN]", username, opened_date, parsed_user_id
        )

    def is_open_thread(self: Self, thread: discord.Thread) -> bool:
        """Check whether a thread is named open and is unlocked.

        Args:
            thread (discord.Thread): The thread to inspect

        Returns:
            bool: Whether the thread is open for modmail changes
        """
        parsed_name = self.parse_modmail_thread_name(thread.name)
        return parsed_name is not None and parsed_name.is_open and not thread.locked

    @property
    def modmail_guild(self: Self) -> discord.Guild:
        """A dynamic fetching of the guild modmail is configured to run in, to ensure no cache misses break modmail

        Returns:
            discord.Guild: The configured guild if it is in TS's cache
        """
        return self.bot.get_guild(
            int(self.bot.file_config.modmail_config.modmail_guild)
        )

    async def get_open_thread(
        self: Self, forum: discord.ForumChannel, user: discord.Member | discord.User
    ) -> discord.Thread | None:
        """Find a user's open thread in the cache, forum, or archived threads.

        Args:
            forum (discord.ForumChannel): The configured modmail forum
            user (discord.Member | discord.User): The user whose thread to find

        Returns:
            discord.Thread | None: The open thread, or None if none exists
        """
        # Assume the existing open thread is actually closed and test it
        existing = self.active_threads.pop(user.id, None)
        # Start by checking non-archived threads and any thread in the active_threads list
        candidates = ([existing] if existing is not None else []) + list(forum.threads)
        checked_ids = set()
        for thread in candidates:
            if thread.id in checked_ids:
                continue
            checked_ids.add(thread.id)
            parsed_name = self.parse_modmail_thread_name(thread.name)
            if parsed_name is None or parsed_name.user_id != user.id:
                continue

            # Cached Thread instances can retain the old name after a rename.
            try:
                thread = await forum.guild.fetch_channel(thread.id)
            except discord.NotFound:
                continue

            parsed_name = self.parse_modmail_thread_name(thread.name)
            if (
                parsed_name is None
                or not parsed_name.is_open
                or parsed_name.user_id != user.id
                or thread.parent_id != forum.id
            ):
                continue

            self.active_threads[user.id] = thread
            return thread

        # If we couldn't find a valid thread, check every archived thread just in case.
        async for thread in forum.archived_threads(limit=None):
            parsed_name = self.parse_modmail_thread_name(thread.name)
            if (
                parsed_name is None
                or parsed_name.user_id != user.id
                or not parsed_name.is_open
            ):
                continue

            self.active_threads[user.id] = thread
            return thread

        # At this point we have checked every thread and found no open threads
        return None

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
        if self.modmail_guild is None:
            raise ValueError("The configured modmail guild is not available to TS.")

        forum_id = int(
            configuration.get_config_entry(
                self.modmail_guild.id, "modmail_forum_channel"
            )
        )

        # We assume the forum channel can be gotten from cache. If not, we try and call the API
        try:
            forum = self.modmail_guild.get_channel(
                forum_id
            ) or await self.modmail_guild.fetch_channel(forum_id)
        except discord.HTTPException:
            raise ValueError("The forum channel is not accessible to me.")

        if not isinstance(forum, discord.ForumChannel):
            raise ValueError("The configured modmail channel must be a forum.")

        return forum

    async def is_banned(self: Self, user: discord.Member) -> bool:
        return await featureban.is_feature_banned(
            self.modmail_guild.id, user.id, featureban.FeatureFlag.MODMAIL
        )

    async def get_modmail_member(self: Self, user_id: int) -> discord.Member | None:
        """This gets a discord.Member object through the main bot's cache or API.
        This should be used over get_modmail_user_object unless access to DMs is needed.

        Args:
            user_id (int): The member's Discord ID

        Returns:
            discord.Member | None: The member, or None if they no longer belong to the guild

        Raises:
            ValueError: The guild is unavailable or Discord cannot fetch the member
        """
        if self.modmail_guild is None:
            raise ValueError("The configured modmail guild is not available to TS.")

        # Default to cache
        member = self.modmail_guild.get_member(user_id)
        if member is not None:
            return member

        # If the member can't be found in cache, try the API
        try:
            return await self.modmail_guild.fetch_member(user_id)
        except discord.NotFound:
            return None
        except discord.HTTPException as exc:
            raise ValueError(
                "The member could not be found due to API errors."
            ) from exc

    async def get_modmail_user_object(self: Self, user_id: int) -> discord.User | None:
        """This gets a discord.User object from the modmail bots perspective.
        This is needed to access DMs

        Args:
            user_id (int): The recipient's Discord ID

        Returns:
            discord.User | None: The recipient, or None if the account cannot be found

        Raises:
            ValueError: Discord cannot fetch the recipient
        """
        recipient = self.bot.modmail_client.get_user(user_id)
        if recipient is not None:
            return recipient

        try:
            return await self.bot.modmail_client.fetch_user(user_id)
        except discord.NotFound:
            return None
        except discord.HTTPException as exc:
            raise ValueError("The user could not be found due to API errors.") from exc

    async def get_paired_dm(
        self: Self, user_id: int, staff_message_id: int
    ) -> discord.Message | None:
        """Fetch the modmail bot's DM paired with a staff message.

        Args:
            user_id (int): The recipient's Discord ID
            staff_message_id (int): The TS message ID in the bidict

        Returns:
            discord.Message | None: The paired DM, or None if its mapping or recipient is missing
        """
        dm_message_id = self.message_id_map.inverse.get(staff_message_id)

        if dm_message_id is None:
            return None

        recipient = await self.get_modmail_user_object(user_id)
        if recipient is None:
            return None

        return await recipient.fetch_message(dm_message_id)

    async def get_staff_copy(
        self: Self, dm_message: discord.Message
    ) -> discord.Message | None:
        """Find a DM's staff copy only while its original thread is open.

        Args:
            message (discord.Message): The source DM

        Returns:
            discord.Message | None: The staff copy, or None if unavailable or closed
        """
        staff_message_id = self.message_id_map.get(dm_message.id)
        if staff_message_id is None:
            return None

        try:
            forum = await self.get_forum()
            thread = await self.get_open_thread(forum, dm_message.author)
        except (discord.HTTPException, ValueError):
            return None

        if thread is None:
            return None

        try:
            return await thread.fetch_message(staff_message_id)
        except discord.NotFound:
            self.message_id_map.pop(dm_message.id, None)
        except discord.HTTPException:
            pass

        return None

    # HELPERS - ACTION

    async def get_reply_command_mention(self: Self) -> str:
        """Resolve the reply command mention from Discord on demand.

        Returns:
            str: The clickable command mention

        Raises:
            discord.HTTPException: Discord cannot fetch the registered commands
            LookupError: The modmail command is not registered
        """
        commands = await self.bot.tree.fetch_commands()

        for command in commands:
            if command.name == self.modmail_commands.name:
                return f"</modmail reply:{command.id}>"

        # In the event the reply command isn't in the command tree
        # This should basically never happen
        raise LookupError("The modmail command is not registered.")

    async def handle_dm(self: Self, message: discord.Message) -> None:
        """Forward a user's DM, opening a thread if needed and allowed.

        Args:
            message (discord.Message): The incoming DM to forward to staff
        """
        try:
            member = await self.get_modmail_member(message.author.id)
        except ValueError as exc:
            await message.channel.send(embed=auxiliary.prepare_deny_embed(str(exc)))
            return

        # This shouldn't be capable of happening, but its here just in case to avoid random errors
        if member is None:
            await message.channel.send(
                embed=auxiliary.prepare_deny_embed(
                    "You must be in the modmail guild to open a thread."
                )
            )
            return

        created = False
        if await self.is_banned(member):
            await message.channel.send(
                embed=auxiliary.prepare_deny_embed("You are banned from modmail.")
            )
            return

        try:
            forum = await self.get_forum()
        except ValueError as exc:
            await message.channel.send(embed=auxiliary.prepare_deny_embed(str(exc)))
            return

        thread = await self.get_open_thread(forum, member)

        # Handle opening a new thread if needed
        if thread is None:
            if self.is_thread_creation_disabled():
                await message.channel.send(
                    embed=auxiliary.prepare_deny_embed(
                        "Modmail thread creation is disabled."
                    )
                )
                return

            try:
                # TODO: Add confirmation prompt here
                thread = await self.create_thread(member)
            except ValueError as exc:
                # A value error should mean the user already has an open thread
                # We check again just in case
                thread = await self.get_open_thread(forum, member)
                if thread is None:
                    await message.channel.send(
                        embed=auxiliary.prepare_deny_embed(str(exc))
                    )
                    return
            else:
                created = True

        await self.send_dm_to_staff(message, thread)

        if created:
            # TODO: Handle auto responses here
            await message.channel.send(
                embed=auxiliary.prepare_confirm_embed(
                    "Your modmail thread has been created."
                )
            )

    async def send_dm_to_staff(
        self: Self, message: discord.Message, thread: discord.Thread
    ) -> None:
        """Forward a user DM to its staff thread.

        Args:
            message (discord.Message): The original DM sent by the user
            thread (discord.Thread): The user's open modmail thread
        """
        if not message.content:
            return

        staff_message = await thread.send(
            view=await self.build_staff_message_view(
                message.author,
                message.content,
                message.created_at,
                message_id=message.id,
            )
        )
        self.message_id_map[message.id] = staff_message.id

    async def send_staff_dm(
        self: Self,
        guild: discord.Guild,
        user: discord.Member,
        author: discord.Member | discord.User,
        message: str,
        timestamp: datetime,
        anonymous: bool = True,
    ) -> discord.Message:
        """Send a copy of the message to the DMs of the target user

        Args:
            guild (discord.Guild): The modmail guild used for anonymous attribution
            user (discord.Member): The recipient of the response
            author (discord.Member | discord.User): The original response author
            message (str): The response text
            timestamp (datetime): The response's original timestamp
            anonymous (bool): Whether to hide the sender's identity in the DM

        Returns:
            discord.Message: The delivered DM for pairing with the staff copy

        Raises:
            ValueError: The response is blank or its recipient is unavailable
        """
        dm_embed = discord.Embed(
            description=message, color=discord.Color.green(), timestamp=timestamp
        )
        dm_embed.set_footer(text="Response")
        dm_embed.set_author(name=str(author), icon_url=author.display_avatar.url)
        automatic = author.id == self.bot.user.id
        if anonymous or automatic:
            dm_embed.set_author(
                name=guild.name if automatic else f"{guild.name} Moderator",
                icon_url=guild.icon.url if guild.icon else None,
            )

        recipient = await self.get_modmail_user_object(user.id)
        if recipient is None:
            raise ValueError("The DM recipient could not be found.")

        channel = await recipient.create_dm()
        sent_message = await channel.send(embed=dm_embed)
        return sent_message

    async def build_staff_message_view(
        self: Self,
        author: discord.Member | discord.User,
        content: str,
        timestamp: datetime,
        user_id: int | None = None,
        anonymous: bool = True,
        message_id: int | None = None,
    ) -> discord.ui.LayoutView:
        """Build the staff conversation message layout and its controls.

        Args:
            author (discord.Member | discord.User): The original sender
            content (str): The message text
            timestamp (datetime): The original message timestamp
            user_id (int | None): The recipient's ID for staff-authored messages
            anonymous (bool): Whether the staff response hides the sender's identity
            message_id (int | None): The source message ID for incoming DMs

        Returns:
            discord.ui.LayoutView: The Components V2 staff conversation message

        Raises:
            ValueError: A staff response contains no text
        """
        staff_source = True if user_id else False

        view = discord.ui.LayoutView(timeout=None)
        color = discord.Color.green() if staff_source else discord.Color.blue()
        container = discord.ui.Container(accent_color=color)
        container.add_item(
            discord.ui.TextDisplay(
                f"### {discord.utils.escape_markdown(author.display_name)}"
            )
        )
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(content))

        if user_id is None:
            metadata = f"Message ID: {message_id}"
        elif author.id == self.bot.user.id:
            metadata = "[Automatic] Response"
        elif anonymous:
            metadata = "[Anonymous] Response"
        else:
            metadata = "Response"

        metadata += f" · {discord.utils.format_dt(timestamp, 'f')}"
        container.add_item(discord.ui.TextDisplay(f"-# {metadata}"))
        container.add_item(discord.ui.Separator())
        container.add_item(
            discord.ui.TextDisplay(await self.get_reply_command_mention())
        )

        # If this message was written by staff, add the buttons
        if staff_source:
            edit = discord.ui.Button(
                label="Edit",
                style=discord.ButtonStyle.primary,
                custom_id="modmail:edit",
            )
            edit.callback = partial(
                self.open_staff_message_editor,
                author=author,
                content=content,
                timestamp=timestamp,
                anonymous=anonymous,
                user_id=user_id,
            )
            delete = discord.ui.Button(
                label="Delete",
                style=discord.ButtonStyle.danger,
                custom_id="modmail:delete",
            )
            delete.callback = partial(
                self.delete_staff_message, user_id=user_id, author_id=author.id
            )
            container.add_item(discord.ui.ActionRow(edit, delete))

        view.add_item(container)
        return view

    async def can_manage_staff_message(
        self: Self,
        interaction: discord.Interaction,
        staff_message: discord.Message,
        author_id: int,
    ) -> bool:
        """This checks to make sure that the edit and delete buttons work only for the appropriate user
        This ensures the thread is open, and the clicking user is the same user who sent the message

        Args:
            interaction (discord.Interaction): The button or modal interaction
            staff_message (discord.Message): The staff message being changed
            author_id (int): The original sender's ID

        Returns:
            bool: Whether the interaction may change the paired messages
        """
        if interaction.user.id != author_id and author_id != self.bot.user.id:
            await interaction.response.send_message(
                "Only the original sender can edit or delete this message.",
                ephemeral=True,
            )
            return False

        # Just in case someone presses a button on a closed thread
        try:
            thread = await self.bot.fetch_channel(staff_message.channel.id)
        except discord.HTTPException:
            thread = None
        if not isinstance(thread, discord.Thread) or not self.is_open_thread(thread):
            await interaction.response.send_message(
                "This modmail thread is closed.", ephemeral=True
            )
            return False

        # If for any reason we can't find the other message, the button should not work
        if staff_message.id not in self.message_id_map.inverse:
            await interaction.response.send_message(
                "The paired DM could not be found. This shouldn't have happened.",
                ephemeral=True,
            )
            return False

        return True

    async def open_staff_message_editor(
        self: Self,
        interaction: discord.Interaction,
        author: discord.Member | discord.User,
        content: str,
        timestamp: datetime,
        anonymous: bool,
        user_id: int,
    ) -> None:
        """This builds, sends and handles the message edit modal

        Args:
            interaction (discord.Interaction): The edit button interaction
            author (discord.Member | discord.User): The original staff sender
            content (str): The current message text
            timestamp (datetime): The original message timestamp
            anonymous (bool): Whether the response hides the sender's identity
            user_id (int): The DM recipient's ID
        """
        if not await self.can_manage_staff_message(
            interaction, interaction.message, author.id
        ):
            return

        modal = discord.ui.Modal(title="Edit message", timeout=300)
        modal.add_item(
            discord.ui.Label(
                text="Message",
                component=discord.ui.TextInput(
                    style=discord.TextStyle.paragraph,
                    default=content[:4000],
                    required=True,
                    max_length=4000,
                ),
            )
        )

        if len(content) > 4000:
            modal.add_item(
                discord.ui.Label(
                    text="Message (continued)",
                    component=discord.ui.TextInput(
                        style=discord.TextStyle.paragraph,
                        default=content[4000:],
                        required=False,
                        max_length=96,
                    ),
                )
            )

        modal.on_submit = partial(
            self.edit_staff_message,
            modal=modal,
            staff_message=interaction.message,
            author=author,
            timestamp=timestamp,
            anonymous=anonymous,
            user_id=user_id,
        )

        await interaction.response.send_modal(modal)

    async def edit_staff_message(
        self: Self,
        interaction: discord.Interaction,
        modal: discord.ui.Modal,
        staff_message: discord.Message,
        author: discord.Member | discord.User,
        timestamp: datetime,
        anonymous: bool,
        user_id: int,
    ) -> None:
        """Edit the message on both the staff side and user side
        This is triggered only by the staff using the edit button

        Args:
            interaction (discord.Interaction): The submitted modal interaction
            modal (discord.ui.Modal): The editor containing the revised text
            staff_message (discord.Message): The TS message being edited
            author (discord.Member | discord.User): The original staff sender
            timestamp (datetime): The original message timestamp
            anonymous (bool): Whether the response hides the sender's identity
            user_id (int): The DM recipient's ID
        """
        # This check should never be hit, but just in case something breaks
        if not await self.can_manage_staff_message(
            interaction, staff_message, author.id
        ):
            return

        content = "".join(
            item.value
            for item in modal.walk_children()
            if isinstance(item, discord.ui.TextInput)
        ).strip()

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            dm_message = await self.get_paired_dm(user_id, staff_message.id)
            if dm_message is None:
                await interaction.followup.send(
                    "The paired DM could not be found.", ephemeral=True
                )
                return
            dm_embed = dm_message.embeds[0].copy()
            dm_embed.description = content
            await dm_message.edit(embed=dm_embed)
            await staff_message.edit(
                view=await self.build_staff_message_view(
                    author, content, timestamp, user_id=user_id, anonymous=anonymous
                ),
            )
        except (discord.HTTPException, ValueError):
            await interaction.followup.send(
                "The message could not be edited on both sides.", ephemeral=True
            )
            return

        await interaction.followup.send("Message edited.", ephemeral=True)

    async def handle_dm_edit(self: Self, message: discord.Message) -> None:
        """Update the staff copy of an edited user DM in an open thread.

        Args:
            message (discord.Message): The edited user DM
        """
        if not message.content:
            return

        staff_message = await self.get_staff_copy(message)
        if staff_message is None:
            return

        try:
            await staff_message.edit(
                view=await self.build_staff_message_view(
                    message.author,
                    message.content,
                    message.created_at,
                    message_id=message.id,
                )
            )
        except discord.HTTPException:
            # TODO: Alert user that the edit could not be applied
            return

    async def handle_dm_delete(self: Self, message: discord.Message) -> None:
        """Mark a deleted DM's staff copy only in an open thread.

        Args:
            message (discord.Message): The deleted user DM
        """
        staff_message = await self.get_staff_copy(message)
        if staff_message is None:
            return

        try:
            await self.mark_staff_message_deleted(staff_message)
        except discord.HTTPException:
            return

    async def mark_staff_message_deleted(
        self: Self, staff_message: discord.Message
    ) -> None:
        """This modifies the view to remove the buttons and add a deleted notice to the staff side

        Args:
            staff_message (discord.Message): The staff copy to update
        """
        view = discord.ui.LayoutView.from_message(staff_message, timeout=None)
        for item in list(view.walk_children()):
            if isinstance(item, discord.ui.ActionRow):
                (item.parent or view).remove_item(item)

        container = next(
            item for item in view.children if isinstance(item, discord.ui.Container)
        )

        container.accent_color = discord.Color.red()
        container.add_item(discord.ui.TextDisplay("This message was deleted"))

        await staff_message.edit(view=view)

    async def delete_staff_message(
        self: Self,
        interaction: discord.Interaction,
        user_id: int,
        author_id: int,
    ) -> None:
        """Delete the DM and mark the preserved staff response as deleted.

        Args:
            interaction (discord.Interaction): The delete button interaction
            user_id (int): The DM recipient's ID
            author_id (int): The original sender's ID
        """
        staff_message = interaction.message
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            try:
                dm_message = await self.get_paired_dm(user_id, staff_message.id)
                if dm_message is None:
                    await interaction.followup.send(
                        "The paired DM could not be found.", ephemeral=True
                    )
                    return
                await dm_message.delete()
            except discord.NotFound:
                pass
            await self.mark_staff_message_deleted(staff_message)
        except (discord.HTTPException, ValueError):
            await interaction.followup.send(
                "The DM could not be deleted or the staff message could not be updated.",
                ephemeral=True,
            )
            return
        await interaction.followup.send("Message deleted.", ephemeral=True)

    async def handle_contact(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        message: str,
    ) -> None:
        """Handle the shared contact and selfcontact creation flow.

        Args:
            interaction (discord.Interaction): The command interaction
            user (discord.Member): The member to create a thread for
            message (str): The message to send to the member
        """
        if interaction.guild_id != self.modmail_guild.id:
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
            timestamp = datetime.now(UTC)
            view = await self.build_staff_message_view(
                interaction.user, message, timestamp, user_id=user.id
            )
            dm_message = await self.send_staff_dm(
                thread.guild, user, interaction.user, message, timestamp
            )
            staff_message = await thread.send(view=view)
            self.message_id_map[dm_message.id] = staff_message.id
        except (ValueError, PermissionError) as exc:
            embed = auxiliary.prepare_deny_embed(str(exc))
        except discord.Forbidden:
            embed = auxiliary.prepare_deny_embed(
                "The message could not be delivered. The user probably has DMs disabled."
            )
        else:
            embed = auxiliary.prepare_confirm_embed(f"Thread created: {thread.mention}")
        await interaction.followup.send(embed=embed)

    async def create_thread(
        self: Self,
        user: discord.Member,
    ) -> discord.Thread:
        """Check for an existing thread and create one under the same async lock.

        Args:
            user (discord.Member): The person the thread is for

        Raises:
            PermissionError: The target user is banned from modmail
            ValueError: The user already has an open thread

        Returns:
            discord.Thread: The newly created thread
        """
        # We use this lock to guarantee to prevent two open threads no matter what
        async with self.thread_creation_lock:
            try:
                forum = await self.get_forum()
            except ValueError as exc:
                raise ValueError(f"Forum channel could not be found: {exc}")
            if await self.is_banned(user):
                raise PermissionError("This user is banned from modmail.")
            existing = await self.get_open_thread(forum, user)
            if existing:
                raise ValueError(
                    f"An open thread for {user.mention} already exists: {existing.mention}"
                )

            past_threads = 0
            async for thread in forum.archived_threads():
                parsed_name = self.parse_modmail_thread_name(thread.name)
                if parsed_name is None or parsed_name.user_id != user.id:
                    continue
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
