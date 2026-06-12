"""All of the discord event listeners where they used for logging"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Self

import discord
from discord.ext import commands

import configuration
from botlogging import LogContext, LogLevel
from core import cogs
from modules.moderation import logger

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Event Logging plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(EventLogger(bot=bot))


class EventEmbed(discord.Embed):
    """This subclass of embed contains several functions to create consistent fields
    for displaying various types of data in the event logs

    Args:
        title (str): The title of the embed to be applied
        description (str): The body of the embed to be applied
    """

    def __init__(self: Self, *, title: str, description: str) -> None:
        super().__init__(
            title=title,
            description=description,
            colour=discord.Colour.orange(),
            timestamp=discord.utils.utcnow(),
        )

    def setEventAuthor(self, author: discord.Member) -> None:
        """This sets an author object of an embed to be stylized as a passed member object
        This shows the display_name and display_avatar

        Args:
            author (discord.Member): The member to make the author of the embed
        """
        self.set_author(
            name=str(author.display_name),
            icon_url=author.display_avatar.url,
        )

    def addMemberField(self: Self, title: str, member: discord.Member) -> None:
        """This adds a member info field to the embed.
        A mention, username, and id are shown here.

        Args:
            title (str): The title of the field
            member (discord.Member): The member object to display information of
        """
        self.add_field(
            name=title,
            value=(
                f"**User:** {member.mention}\n"
                f"**Name:** {member.name}\n"
                f"**ID:** {member.id}"
            ),
            inline=True,
        )

    def addMessageContentField(
        self: Self, title: str, message: discord.Message
    ) -> None:
        """This adds a message content info field to the embed.
        Clean content, trimmed to 1024 in size, is what is used.

        Args:
            title (str): The title of the field
            message (discord.Message): The message object to get the content from
        """
        if not message.clean_content:
            content = "*No content*"
        elif len(message.clean_content) > 1024:
            content = message.clean_content[:1021] + "..."
        else:
            content = message.clean_content
        self.add_field(
            name=title,
            value=content,
            inline=True,
        )

    def addMessageInfoField(self: Self, title: str, message: discord.Message) -> None:
        """This adds a message info field to the embed.
        Clean content, trimmed to 50, the author, the ID, and the sent at time are all displayed

        Args:
            title (str): The title of the field
            message (discord.Message): The message object to get the information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Message Content:** {message.clean_content[:50]}\n"
                f"**Message Author:** {message.author.name} ({message.author.mention})\n"
                f"**Message ID:** {message.id}\n"
                f"**Sent:** <t:{int(message.created_at.timestamp())}:F> "
                f"(<t:{int(message.created_at.timestamp())}:R>)"
            ),
        )

    def addChannelField(
        self: Self, title: str, channel: discord.abc.GuildChannel
    ) -> None:
        """This adds a channel info field into the embed.
        Channel link, name, type and ID are all displayed.

        Args:
            title (str): The title of the field
            channel (discord.abc.GuildChannel): The channel object to get information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Channel:** {channel.mention}\n"
                f"**Name:** #{channel.name}\n"
                f"**Type:** {channel.type.name}\n"
                f"**ID:** {channel.id}"
            ),
            inline=True,
        )

    def addSoundboardField(
        self: Self, title: str, soundboard: discord.SoundboardSound
    ) -> None:
        """This adds a soundboard info field into the embed.
        Name, volume, emoji and ID are all displayed.

        Args:
            title (str): The title of the field
            soundboard (discord.SoundboardSound): The soundboard object to get information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Name:** {soundboard.name}\n"
                f"**Volume:** {soundboard.volume}\n"
                f"**Emoji:** {soundboard.emoji}\n"
                f"**ID:** {soundboard.id}"
            ),
            inline=True,
        )

    def addEmojiField(
        self: Self, title: str, emoji: discord.Emoji | discord.PartialEmoji | str
    ) -> None:
        """This adds an emoji info field into the embed.
        For standard reactions, just the emoji is displayed.
        For custom emojis, the emoji will attempt to be displayed, as well as the name and ID

        Args:
            title (str): The title of the field
            emoji (discord.Emoji | discord.PartialEmoji | str):
                The emoji object to get information from
        """
        # This is to better display custom emotes
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            emoji_value = (
                f"**Emoji:** {emoji}\n"
                f"**Name:** {emoji.name}\n"
                f"**ID:** {emoji.id}"
            )
        else:
            emoji_value = f"**Emoji:** {emoji}"

        self.add_field(name=title, value=emoji_value)

    def addStickerField(
        self: Self,
        title: str,
        sticker: discord.GuildSticker,
    ) -> None:
        """This adds a sticker info field into the embed.
        Name, ID, description and emoji are all displayed.

        Args:
            title (str): The title of the field
            sticker (discord.GuildSticker): The sticker object to get information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Name:** {sticker.name}\n"
                f"**ID:** {sticker.id}\n"
                f"**Description:** {sticker.description or 'None'}\n"
                f"**Emoji:** {sticker.emoji or 'None'}"
            ),
        )

    def addIntegrationField(
        self: Self,
        title: str,
        integration: discord.Integration,
    ) -> None:
        """This adds an integration info field into the embed.
        Name, type, scope and ID are all displayed

        Args:
            title (str): The title of the field
            integration (discord.Integration): The integration object to get information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Name:** {integration.name}\n"
                f"**Type:** {integration.type}\n"
                f"**Scope:** {integration.scopes}\n"
                f"**ID:** {integration.id}"
            ),
        )

    def addPollField(self: Self, title: str, poll: discord.Poll) -> None:
        """This adds a poll info field into the embed.
        Question, duration, and answers are all displayed.

        Args:
            title (str): The title of the field
            poll (discord.Poll): The poll object to get information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Question:** {poll.question}\n"
                f"**Duration:** {poll.duration}\n"
                f"**Answers:** {', '.join([answer.text for answer in poll.answers])}"
            ),
            inline=True,
        )

    def addPollAnswerField(self: Self, title: str, answer: discord.PollAnswer) -> None:
        """This adds a poll answer info field into the embed. The answer and ID are both displayed.

        Args:
            title (str): The title of the field
            answer (discord.PollAnswer): The answer object to get information from
        """
        self.add_field(
            name=title,
            value=(f"**Answer:** {answer.text}\n**ID:** {answer.id}"),
            inline=True,
        )

    def addRoleField(self: Self, title: str, role: discord.Role) -> None:
        """This adds a role info field into the embed.
        Mention, name, ID, position, hoisted and mentionable status are all displayed.

        Args:
            title (str): The title of the field
            role (discord.Role): The role object to get information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Role:** {role.mention}\n"
                f"**Name:** {role.name}\n"
                f"**ID:** {role.id}\n"
                f"**Position:** {role.position}\n"
                f"**Hoisted:** {'Yes' if role.hoist else 'No'}\n"
                f"**Mentionable:** {'Yes' if role.mentionable else 'No'}"
            ),
            inline=True,
        )

    def addRoleMetadataField(self: Self, title: str, role: discord.Role) -> None:
        """This adds a role metadata field into the embed.
        Timestamp, tags, flags, and icon are displayed

        Args:
            title (str): The title of the field
            role (discord.Role): The role object to get information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Created:** <t:{int(role.created_at.timestamp())}:F> "
                f"(<t:{int(role.created_at.timestamp())}:R>)\n"
                f"**Tags:** {role.tags or 'None'}\n"
                f"**Flags:** {role.flags}\n"
                f"**Icon:** {role.icon or 'None'}\n"
                f"**Display Icon:** {role.display_icon or 'None'}"
            ),
            inline=True,
        )

    def addRoleColorField(self: Self, title: str, role: discord.Role) -> None:
        """This adds a role color field into the embed.
        Primary, secondary, and tertiary colors are all displayed.

        Args:
            title (str): The title of the field
            role (discord.Role): The role object to get information from
        """
        self.add_field(
            name=title,
            value=(
                f"**Primary:** {role.colour}\n"
                f"**Secondary:** {role.secondary_colour}\n"
                f"**Tertiary:** {role.tertiary_colour}"
            ),
            inline=True,
        )

    def addScheduledEventField(
        self: Self, title: str, event: discord.ScheduledEvent
    ) -> None:
        """This adds a scheduled event field into the embed.
        Time, ID, status, location are all included.

        Args:
            title (str): The title of the field
            event (discord.ScheduledEvent): The event object to get information from
        """
        start_time = (
            f"<t:{int(event.start_time.timestamp())}:F> "
            f"(<t:{int(event.start_time.timestamp())}:R>)"
            if event.start_time
            else "None"
        )
        end_time = (
            f"<t:{int(event.end_time.timestamp())}:F> "
            f"(<t:{int(event.end_time.timestamp())}:R>)"
            if event.end_time
            else "None"
        )
        location = event.channel.mention if event.channel else event.location or "None"

        self.add_field(
            name=title,
            value=(
                f"**Name:** {event.name}\n"
                f"**ID:** {event.id}\n"
                f"**Status:** {event.status}\n"
                f"**Entity Type:** {event.entity_type}\n"
                f"**Location:** {location}\n"
                f"**Start:** {start_time}\n"
                f"**End:** {end_time}"
            ),
            inline=True,
        )

    def addAutoModRuleField(self: Self, title: str, rule: discord.AutoModRule) -> None:
        """This adds an automod rule info field into the embed.
        Name, ID, status, type, triggers, actions, and exempt info are all displayed

        Args:
            title (str): The title of the field
            rule (discord.AutoModRule): The automod object to get information from
        """
        actions = ", ".join(str(action.type) for action in rule.actions) or "None"
        if len(actions) > 200:
            actions = actions[:197] + "..."

        self.add_field(
            name=title,
            value=(
                f"**Name:** {rule.name}\n"
                f"**ID:** {rule.id}\n"
                f"**Enabled:** {'Yes' if rule.enabled else 'No'}\n"
                f"**Event Type:** {rule.event_type}\n"
                f"**Trigger:** {rule.trigger.type}\n"
                f"**Actions:** {actions}\n"
                f"**Exempt Roles:** {len(rule.exempt_role_ids)}\n"
                f"**Exempt Channels:** {len(rule.exempt_channel_ids)}"
            ),
            inline=True,
        )

    def addRolePermissionChangeFields(
        self: Self, before: discord.Permissions, after: discord.Permissions
    ) -> bool:
        """This adds fields displaying permissions changes between two roles

        Args:
            before (discord.Permissions): The old set of permissions
            after (discord.Permissions): The new set of permissions

        Returns:
            bool: Whether anything was added to the embed
        """
        added: list[str] = []
        removed: list[str] = []
        changed: list[str] = []

        before_permissions = dict(iter(before))
        after_permissions = dict(iter(after))
        all_permissions = set(before_permissions) | set(after_permissions)

        for permission in sorted(all_permissions):
            old = before_permissions.get(permission)
            new = after_permissions.get(permission)

            if old == new:
                continue

            permission_name = permission.replace("_", " ").title()

            if old is None:
                added.append(f"✅ `{permission_name}` → {new}")
            elif new is None:
                removed.append(f"❌ `{permission_name}` (was {old})")
            else:
                old_emoji = "✅" if old else "❌"
                new_emoji = "✅" if new else "❌"
                changed.append(f"➖ `{permission_name}` {old_emoji} → {new_emoji}")

        if not (added or removed or changed):
            return False

        value_parts = []

        if added:
            value_parts.append("**Added**\n" + "\n".join(added))

        if removed:
            value_parts.append("**Removed**\n" + "\n".join(removed))

        if changed:
            value_parts.append("**Changed**\n" + "\n".join(changed))

        value = "\n\n".join(value_parts)

        if len(value) > 1024:
            value = value[:1021] + "..."

        self.add_field(
            name="Permissions",
            value=value,
            inline=False,
        )

        return True

    def addPropertyChangeFields(
        self: Self, properties: list[str], before: Any, after: Any  # noqa: ANN401
    ) -> bool:
        """Adds fields to the embed for an arbitrary list of string properties
            to compare betweeen two objects

        Args:
            properties (list[str]): A list of properties to get and compared
            before (Any): The old object before any changes were made
            after (Any): The new object after all changes were made

        Returns:
            bool: Whether anything was added to the embed
        """
        changes = []

        for attr in properties:
            old_value = getattr(before, attr, None)
            new_value = getattr(after, attr, None)

            # If both are lists, sort them before comparing
            if isinstance(old_value, list) and isinstance(new_value, list):
                old_compare = sorted(old_value, key=str)
                new_compare = sorted(new_value, key=str)
            else:
                old_compare = old_value
                new_compare = new_value

            if old_compare != new_compare:
                changes.append((attr, old_value, new_value))

        if changes:
            for attr, old_value, new_value in changes:
                # Make the property name prettier
                field_name = attr.replace("_", " ").title()

                # Special formatting for categories
                if attr == "category":
                    old_value = old_value.mention if old_value else "None"
                    new_value = new_value.mention if new_value else "None"

                # Better formatting for booleans
                elif isinstance(old_value, bool):
                    old_value = "Yes" if old_value else "No"
                    new_value = "Yes" if new_value else "No"

                self.add_field(
                    name=field_name,
                    value=f"**Old:** {old_value}\n**New:** {new_value}",
                    inline=True,
                )

            return True

        return False


class EventLogger(cogs.BaseCog):
    """This is the cog that holds all of the discord event listeners
    For the explicit purpose of logging, not taking further action

    Attrs:
        CONFIG_MAP (dict[str, str]): A mpa of types of logs to the config names
            of their respective logging channel
    """

    CONFIG_MAP: dict[str, str] = {
        "bot": "core_logging_channel",
        "guild": "core_guild_events_channel",
        "member": "core_member_events_channel",
        "message": "core_message_events_channel",
    }

    async def send_event_log(
        self: Self,
        guild: discord.Guild,
        log_location: str,
        string_message: str,
        embed_message: discord.Embed,
        channel_location: discord.abc.GuildChannel = None,
    ) -> None:
        """This sends a log to discord and the console for the event

        Args:
            guild (discord.Guild): The guild the event happened in
            log_location (str): The location to log, string in CONFIG_MAP
            string_message (str): The string message to send to the console
            embed_message (discord.Embed): The embed to send to the configured log channel
            channel_location (discord.abc.GuildChannel, optional):
                The channel the event happened in, if applicable. Defaults to None.
        """

        # Do nothing if events is disabled in current guild
        if not self.extension_enabled(guild):
            return

        context = LogContext(guild=guild, channel=channel_location)
        message_header = f"Events for {guild.name} ({guild.id}): "
        log_channel = self.CONFIG_MAP[log_location]
        log_channel_id = configuration.get_config_entry(guild.id, log_channel)
        await self.bot.logger.send_log(
            message=message_header + string_message,
            level=LogLevel.INFO,
            context=context,
            channel=log_channel_id,
            embed=embed_message,
            embed_as_is=True,
        )

    # Message events

    @commands.Cog.listener()
    async def on_message_edit(
        self: Self, before: discord.Message, after: discord.Message
    ) -> None:
        """This logs message content edit and message (un)pin events
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_edit

        Args:
            before (discord.Message): The original message, before the edit occured
            after (discord.Message): The new message, after it is been edited
        """
        # If for some reason there is no message object, log nothing
        if not after or not before:
            return

        guild = getattr(after.channel, "guild", None)

        # Ignore all message edit events in DMs
        if not guild:
            return

        # Ignore ephemeral slash command messages
        if after.type == discord.MessageType.chat_input_command:
            return

        # Message edits for content edit:
        if before.content != after.content:
            embed = EventEmbed(
                title="Message edited",
                description=f"[Jump to Message]({after.jump_url})",
            )

            embed.setEventAuthor(after.author)
            embed.addMemberField("Message Author", after.author)
            embed.addChannelField("Channel", after.channel)

            old_content = before.clean_content
            embed.addMessageContentField("Old Content", before)
            embed.addMessageContentField("New Content", after)

            # Custom field for this event
            embed.add_field(
                name="Timestamps",
                value=(
                    f"**Sent:** <t:{int(after.created_at.timestamp())}:F> "
                    f"(<t:{int(after.created_at.timestamp())}:R>)\n"
                    f"**Edited:** <t:{int(after.edited_at.timestamp())}:F> "
                    f"(<t:{int(after.edited_at.timestamp())}:R>)"
                ),
                inline=False,
            )

            embed.set_footer(text=f"Message ID: {after.id}")

            console_message = (
                f"Message edit: ID: {after.id} in channel: {after.channel.name} "
                f"({after.channel.id}). Old: {old_content}, new {after.clean_content}"
            )

            await self.send_event_log(
                guild=after.guild,
                log_location="message",
                string_message=console_message,
                embed_message=embed,
                channel_location=after.channel,
            )

        # Message edits for pin update:
        if before.pinned != after.pinned:

            title = "Message pinned" if after.pinned else "Message unpinned"
            embed = EventEmbed(
                title=title,
                description=f"[Jump to Message]({after.jump_url})",
            )

            embed.setEventAuthor(after.author)
            embed.addMemberField("Message Author", after.author)
            embed.addChannelField("Channel", after.channel)
            embed.addMessageContentField("Content", after)

            embed.set_footer(text=f"Message ID: {after.id}")

            console_message = (
                f"Message pins changed: ID: {after.id} in channel: "
                f"{after.channel.name} ({after.channel.id}). Pinned status: {after.pinned}"
            )

            await self.send_event_log(
                guild=after.guild,
                log_location="message",
                string_message=console_message,
                embed_message=embed,
                channel_location=after.channel,
            )

    @commands.Cog.listener()
    async def on_message_delete(self: Self, message: discord.Message) -> None:
        """This logs message delete events, by both users and moderators
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_delete

        Args:
            message (discord.Message): The message that was deleted
        """
        guild = message.guild
        channel = message.channel

        # Ignore ephemeral slash command messages
        if message.type == discord.MessageType.chat_input_command:
            return

        embed = EventEmbed(
            title="Message deleted",
            description=f"[Jump to Message]({message.jump_url})",
        )

        embed.setEventAuthor(message.author)
        embed.addMemberField("Message Author", message.author)
        embed.addChannelField("Channel", message.channel)
        embed.addMessageContentField("Content", message)

        embed.add_field(
            name="Message Sent",
            value=(
                f"<t:{int(message.created_at.timestamp())}:F> "
                f"(<t:{int(message.created_at.timestamp())}:R>)"
            ),
            inline=False,
        )

        embed.set_footer(text=f"Message ID: {message.id}")

        console_message = (
            f"Message delete: ID: {message.id} in channel: "
            f"{channel.name} ({channel.id}). Content: {message.clean_content}"
        )

        await self.send_event_log(
            guild=guild,
            log_location="message",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    @commands.Cog.listener()
    async def on_bulk_message_delete(
        self: Self, messages: list[discord.Message]
    ) -> None:
        """This logs bulk message delete events, such as those by a purge command or ban
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_bulk_message_delete

        Args:
            messages (list[discord.Message]): The list of message objects that have been deleted
        """
        channel = messages[0].channel
        guild = channel.guild

        # Don't log stuff not in a guild
        if not guild:
            return

        embed = EventEmbed(
            title="Bulk message delete",
            description="",
        )
        embed.addChannelField("Channel", channel)

        description_prefix = f"{len(messages)} messages were deleted:\n"

        max_embed_length = 4096
        content_limit = 100

        while True:
            lines: list[str] = []

            for message in messages:
                clean_content = message.clean_content

                if len(clean_content) > content_limit:
                    clean_content = f"{clean_content[:content_limit]}..."

                lines.append(f"{message.id}, {message.author.name}: {clean_content}")

            description = description_prefix + "\n".join(lines)

            if len(description) <= max_embed_length or content_limit <= 0:
                break

            content_limit -= 1

        embed.description = description

        console_message = (
            f"Bulk message delete: Channel: {channel.name} "
            f"({channel.id}). Amount: {len(messages)}"
        )

        await self.send_event_log(
            guild=guild,
            log_location="message",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    @commands.Cog.listener()
    async def on_reaction_add(
        self: Self, reaction: discord.Reaction, user: discord.Member | discord.User
    ) -> None:
        """This logs events where a reaction has been added to a message
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_add

        Args:
            reaction (discord.Reaction): The reaction object that was added
            user (discord.Member | discord.User): The account that added the reaction
        """
        message = reaction.message
        channel = message.channel
        guild = getattr(channel, "guild", None)

        if isinstance(channel, discord.DMChannel):
            await self.bot.logger.send_log(
                message=(
                    f"PM from `{user}`: added {reaction.emoji} reaction to message"
                    f" {message.content} in DMs"
                ),
                level=LogLevel.INFO,
            )
            return

        if not guild:
            return

        embed = EventEmbed(
            title="Reaction added",
            description=f"[Jump to Message]({message.jump_url})",
        )

        embed.setEventAuthor(user)
        embed.addEmojiField("Emoji", reaction.emoji)
        embed.addMemberField("Message Author", user)
        embed.addChannelField("Channel", message.channel)
        embed.addMessageInfoField("Message Info", message)

        console_message = (
            f"Reaction {reaction.emoji} added to message with "
            f"ID: {message.id} by user {user.name} ({user.id})"
        )

        await self.send_event_log(
            guild=guild,
            log_location="message",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    @commands.Cog.listener()
    async def on_reaction_remove(
        self: Self, reaction: discord.Reaction, user: discord.Member | discord.User
    ) -> None:
        """This logs events where a reaction has been removed from a message
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_remove

        Args:
            reaction (discord.Reaction): The reaction object that was removed
            user (discord.Member | discord.User): The account that originally had that reaction
        """
        message = reaction.message
        channel = message.channel
        guild = getattr(channel, "guild", None)

        if isinstance(channel, discord.DMChannel):
            await self.bot.logger.send_log(
                message=(
                    f"PM from `{user}`: added {reaction.emoji} reaction to message"
                    f" {message.content} in DMs"
                ),
                level=LogLevel.INFO,
            )
            return

        if not guild:
            return

        embed = EventEmbed(
            title="Reaction removed",
            description=f"[Jump to Message]({message.jump_url})",
        )

        embed.setEventAuthor(user)
        embed.addEmojiField("Emoji", reaction.emoji)
        embed.addMemberField("Message Author", user)
        embed.addChannelField("Channel", message.channel)
        embed.addMessageInfoField("Message Info", message)

        console_message = (
            f"Reaction {reaction.emoji} removed from message "
            f"with ID: {message.id} by user {user.name} ({user.id})"
        )

        await self.send_event_log(
            guild=guild,
            log_location="message",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    @commands.Cog.listener()
    async def on_reaction_clear(
        self: Self, message: discord.Message, reactions: list[discord.Reaction]
    ) -> None:
        """This logs events where all reactions or all of a specific reaction
            were cleared from a message
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_clear

        Args:
            message (discord.Message): The messages reactions were cleared from
            reactions (list[discord.Reaction]): The reactions that were removed
        """
        guild = getattr(message.channel, "guild", None)
        channel = message.channel

        # Don't log messages without a guild
        if not guild:
            return

        emoji_str = ""
        total_emoji = 0
        for reaction in reactions:
            emoji_str += f"`{reaction.emoji}`: {reaction.count}\n"
            total_emoji += reaction.count

        embed = EventEmbed(
            title="Reactions cleared",
            description=f"[Jump to Message]({message.jump_url})",
        )

        embed.add_field(name="Emojis", value=emoji_str)

        embed.addChannelField("Channel", message.channel)
        embed.addMessageInfoField("Message Info", message)

        console_message = (
            f"{total_emoji} reactions cleared from message with "
            f"ID: {message.id} in channel {channel.name} ({channel.id})"
        )

        await self.send_event_log(
            guild=guild,
            log_location="message",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    @commands.Cog.listener()
    async def on_poll_vote_add(
        self: Self, user: discord.Member, answer: discord.PollAnswer
    ) -> None:
        """This logs events where a user has voted in a poll
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_poll_vote_add

        Args:
            user (discord.Member): The user who voted in the poll
            answer (discord.PollAnswer): The answer selected in the poll
        """
        if not user.guild:
            return

        guild = user.guild
        message = answer.poll.message
        channel = message.channel

        embed = EventEmbed(
            title="Poll answered",
            description=f"[Jump to Message]({message.jump_url})",
        )

        embed.setEventAuthor(user)
        embed.addPollField("Poll", answer.poll)
        embed.addPollAnswerField("Answer", answer)
        embed.addChannelField("Channel", channel)
        embed.addMemberField("Member", user)
        embed.addMessageInfoField("Message", message)

        console_message = (
            f"User {user.name} ({user.id}) voted {answer.text} "
            f"to poll message {message.id} in channel {channel.name} ({channel.id})"
        )

        await self.send_event_log(
            guild=guild,
            log_location="message",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    @commands.Cog.listener()
    async def on_poll_vote_remove(
        self: Self, user: discord.Member, answer: discord.PollAnswer
    ) -> None:
        """This logs events where a user has removed their vote in a poll
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_poll_vote_remove

        Args:
            user (discord.Member): The user who voted in the poll
            answer (discord.PollAnswer): The answer removed in the poll
        """
        if not user.guild:
            return

        guild = user.guild
        message = answer.poll.message
        channel = message.channel

        embed = EventEmbed(
            title="Poll answer removed",
            description=f"[Jump to Message]({message.jump_url})",
        )

        embed.setEventAuthor(user)
        embed.addPollField("Poll", answer.poll)
        embed.addPollAnswerField("Answer", answer)
        embed.addChannelField("Channel", channel)
        embed.addMemberField("Member", user)
        embed.addMessageInfoField("Message", message)

        console_message = (
            f"User {user.name} ({user.id}) removed vote {answer.text} "
            f"from a poll message {message.id} in channel {channel.name} ({channel.id})"
        )

        await self.send_event_log(
            guild=guild,
            log_location="message",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    # Member events

    @commands.Cog.listener()
    async def on_member_join(self: Self, member: discord.Member) -> None:
        """This logs events where new members have joined the guild
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join

        Args:
            member (discord.Member): The member who has joined
        """
        embed = EventEmbed(
            title="Member joined",
            description="",
        )

        embed.setEventAuthor(member)
        embed.addMemberField("New Member", member)

        if member.flags.did_rejoin:
            embed.set_footer(text="This user has joined this server before")

        console_message = f"Member joined: {member.name} ({member.id})"

        await self.send_event_log(
            guild=member.guild,
            log_location="member",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_raw_member_remove(
        self: Self, payload: discord.RawMemberRemoveEvent
    ) -> None:
        """This logs events where members left or are kicked/banned from the guild.
        This is a raw listener, so it does not rely on the cache to get this callout
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_member_remove

        Args:
            payload (discord.RawMemberRemoveEvent): The member who left the service
        """
        member = payload.user
        embed = EventEmbed(
            title="Member left",
            description="",
        )

        embed.setEventAuthor(member)
        embed.addMemberField("Member", member)

        if isinstance(member, discord.Member):
            embed.add_field(
                name="Joined at",
                value=(
                    f"<t:{int(member.joined_at.timestamp())}:F> "
                    f"(<t:{int(member.joined_at.timestamp())}:R>)"
                ),
            )
            embed.add_field(
                name="Roles",
                value=", ".join(logger.generate_role_list(member)),
            )

        # If member object, show roles and date joined?

        console_message = f"Member left: {member.name} ({member.id})"

        await self.send_event_log(
            guild=member.guild,
            log_location="member",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self: Self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """This logs events related to server (un)mute/deafing of members
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_voice_state_update

        Args:
            member (discord.Member): The member who had their account changed
            before (discord.VoiceState): The previous state of the members voice account
            after (discord.VoiceState): The new state of the members voice account
        """
        # We need to handle server deafen and server mute
        if before.mute != after.mute:
            embed = EventEmbed(
                title=f"Member Server {'un' if before.mute else ''}muted",
                description="",
            )

            embed.setEventAuthor(member)
            embed.addMemberField("Member", member)

            if after.channel:
                embed.addChannelField("Current Channel", after.channel)

            console_message = f"{embed.title}: {member.name} ({member.id})"

            await self.send_event_log(
                guild=member.guild,
                log_location="member",
                string_message=console_message,
                embed_message=embed,
                channel_location=after.channel,
            )

        if before.deaf != after.deaf:
            embed = EventEmbed(
                title=f"Member Server {'un' if before.deaf else ''}deafened",
                description="",
            )

            embed.setEventAuthor(member)
            embed.addMemberField("Member", member)

            if after.channel:
                embed.addChannelField("Current Channel", after.channel)

            console_message = f"{embed.title}: {member.name} ({member.id})"

            await self.send_event_log(
                guild=member.guild,
                log_location="member",
                string_message=console_message,
                embed_message=embed,
            )

    @commands.Cog.listener()
    async def on_user_update(
        self: Self, before: discord.User, after: discord.User
    ) -> None:
        """This logs events related to username and display name changes
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_user_update

        Args:
            before (discord.User): The old user account object, before changes
            after (discord.User): The new user account object, after changes
        """
        # We want to track name and global name changes
        if before.name != after.name:
            embed = EventEmbed(
                title="Member username changed",
                description="",
            )

            embed.setEventAuthor(after)
            embed.addMemberField("Member", after)
            embed.add_field(
                name="name:", value=f"**Old:** {before.name}\n**New:** {after.name}"
            )

            console_message = f"Member changed their name: {after.name} ({after.id})"

            for guild in after.mutual_guilds:
                await self.send_event_log(
                    guild=guild,
                    log_location="member",
                    string_message=console_message,
                    embed_message=embed,
                )

        if before.global_name != after.global_name:
            embed = EventEmbed(
                title="Member global name changed",
                description="",
            )

            embed.setEventAuthor(after)
            embed.addMemberField("Member", after)
            embed.add_field(
                name="global_name:",
                value=f"**Old:** {before.global_name}\n**New:** {after.global_name}",
            )

            console_message = (
                f"Member changed their global_name: {after.name} ({after.id})"
            )

            for guild in after.mutual_guilds:
                await self.send_event_log(
                    guild=guild,
                    log_location="member",
                    string_message=console_message,
                    embed_message=embed,
                )

    @commands.Cog.listener()
    async def on_member_update(
        self: Self, before: discord.Member, after: discord.Member
    ) -> None:
        """This logs events related to nickname changes and member role changes
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_update

        Args:
            before (discord.Member): The old member object, pre changes
            after (discord.Member): The new member object, post changes
        """
        # We want to track role and nickname changes

        if before.nick != after.nick:
            embed = EventEmbed(
                title="Member nickname changed",
                description="",
            )

            embed.setEventAuthor(after)
            embed.addMemberField("Member", after)
            embed.add_field(
                name="nick:",
                value=f"**Old:** {before.nick}\n**New:** {after.nick}",
            )

            console_message = f"Member changed their nick: {after.name} ({after.id})"

            await self.send_event_log(
                guild=after.guild,
                log_location="member",
                string_message=console_message,
                embed_message=embed,
            )

        roles_lost = set(before.roles) - set(after.roles)
        roles_gained = set(after.roles) - set(before.roles)
        changed_role = set(before.roles) ^ set(after.roles)
        if changed_role:
            embed = EventEmbed(
                title="Member roles updated",
                description="",
            )
            embed.setEventAuthor(after)
            embed.addMemberField("Member", after)

            if roles_gained:
                embed.add_field(
                    name="Roles added",
                    value=", ".join([role.mention for role in roles_gained]),
                )

            if roles_lost:
                embed.add_field(
                    name="Roles removed",
                    value=", ".join([role.mention for role in roles_lost]),
                )

            console_message = (
                f"Member roles updated: {after.name} ({after.id}). "
                f"Roles changed {', '.join(role.name for role in changed_role)}"
            )

            await self.send_event_log(
                guild=after.guild,
                log_location="member",
                string_message=console_message,
                embed_message=embed,
            )

    # Guild events

    @commands.Cog.listener()
    async def on_guild_channel_create(
        self: Self, channel: discord.abc.GuildChannel
    ) -> None:
        """This logs events to GuildChannel objects being created
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_create

        Args:
            channel (discord.abc.GuildChannel): The channel object that was created.
        """
        embed = EventEmbed(
            title="Channel created",
            description="",
        )

        embed.addChannelField("Channel", channel)

        console_message = f"Channel {channel.name} ({channel.id}) was created"

        await self.send_event_log(
            guild=channel.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self: Self, channel: discord.abc.GuildChannel
    ) -> None:
        """This logs events to GuildChannel objects being deleted
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_delete

        Args:
            channel (discord.abc.GuildChannel): The channel object that was deleted.
        """
        embed = EventEmbed(
            title="Channel deleted",
            description="",
        )

        embed.addChannelField("Channel", channel)

        console_message = f"Channel {channel.name} ({channel.id}) was deleted"

        await self.send_event_log(
            guild=channel.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
            channel_location=channel,
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self: Self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ) -> None:
        """This logs events related to property changes to guild channels.
        A seperate event is logged for channel permission changes
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_update

        Args:
            before (discord.abc.GuildChannel): The previous channel, before any changes
            after (discord.abc.GuildChannel): The new channel, after any changes
        """

        # This is hell. Thanks claude
        if before.overwrites != after.overwrites:
            embed = EventEmbed(
                title="Channel permissions updated",
                description="",
            )

            embed.addChannelField("Channel", after)

            console_changes: list[str] = []

            all_targets = set(before.overwrites) | set(after.overwrites)

            for target in all_targets:
                before_overwrite = before.overwrites.get(
                    target, discord.PermissionOverwrite()
                )
                after_overwrite = after.overwrites.get(
                    target, discord.PermissionOverwrite()
                )

                before_perms = dict(before_overwrite)
                after_perms = dict(after_overwrite)

                added: list[str] = []
                removed: list[str] = []
                changed: list[str] = []

                all_permissions = set(before_perms) | set(after_perms)

                for permission in sorted(all_permissions):
                    old = before_perms.get(permission)
                    new = after_perms.get(permission)

                    if old == new:
                        continue

                    if old is None:
                        added.append(
                            f"✅ `{permission.replace('_', ' ').title()}` → {new}"
                        )
                    elif new is None:
                        removed.append(
                            f"❌ `{permission.replace('_', ' ').title()}` (was {old})"
                        )
                    else:
                        old_emoji = "✅" if old else "❌"
                        new_emoji = "✅" if new else "❌"

                        changed.append(
                            f"➖ `{permission.replace('_', ' ').title()}` "
                            f"{old_emoji} → {new_emoji}"
                        )

                if not (added or removed or changed):
                    continue

                value_parts = []

                if isinstance(target, discord.Role):
                    target_name = "Role:"
                    value_parts.append(f"{target.mention}")
                elif isinstance(target, discord.Member):
                    target_name = "Member:"
                    value_parts.append(f"{target.mention}")
                else:
                    target_name = "Unknown:"
                    value_parts.append(f"{target.id}")

                if added:
                    value_parts.append("**Added**\n" + "\n".join(added))

                if removed:
                    value_parts.append("**Removed**\n" + "\n".join(removed))

                if changed:
                    value_parts.append("**Changed**\n" + "\n".join(changed))

                value = "\n\n".join(value_parts)

                # Discord field value limit
                if len(value) > 1024:
                    value = value[:1021] + "..."

                embed.add_field(
                    name=target_name,
                    value=value,
                    inline=False,
                )

                console_changes.append(target_name)

            if not console_changes:
                return

            console_message = (
                "Permission overwrites updated for channel "
                f"{after.name} ({after.id})"
            )

            await self.send_event_log(
                guild=after.guild,
                log_location="guild",
                string_message=console_message,
                embed_message=embed,
                channel_location=after,
            )

        properties_to_track = [
            "category",
            "name",
            "permissions_synced",
            "position",
            "topic",
            "slowmode_delay",
            "bitrate",
            "user_limit",
            "nsfw",
            "rtc_region",
            "type",
        ]
        embed = EventEmbed(title="Channel properties updated", description="")
        embed.addChannelField("Channel", after)

        if embed.addPropertyChangeFields(properties_to_track, before, after):
            console_message = (
                f"Channel properties updated for channel " f"{after.name} ({after.id})"
            )

            await self.send_event_log(
                guild=after.guild,
                log_location="guild",
                string_message=console_message,
                embed_message=embed,
                channel_location=after,
            )

    @commands.Cog.listener()
    async def on_guild_update(
        self: Self, before: discord.Guild, after: discord.Guild
    ) -> None:
        """This logs a huge number of property changes for a given guild
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_update

        Args:
            before (discord.Guild): The old guild state, before any property changes
            after (discord.Guild): The new guild state, after any property changes
        """
        properties_to_track = [
            "afk_channel",
            "afk_timeout",
            "banner",
            "bitrate_limit",
            "categories",
            "description",
            "default_notifications",
            "dms_paused_until",
            "discovery_splash",
            "emoji_limit",
            "explicit_content_filter",
            "features",
            "filesize_limit",
            "icon",
            "invites_paused_until",
            "mfa_level",
            "name",
            "nsfw_level",
            "owner",
            "preferred_locale",
            "premium_tier",
            "public_updates_channel",
            "rules_channel",
            "safety_alerts_channel",
            "splash",
            "system_channel",
            "verification_level",
        ]
        embed = EventEmbed(title="Guild properties updated", description="")

        if embed.addPropertyChangeFields(properties_to_track, before, after):
            console_message = "Guild properties updated."

            await self.send_event_log(
                guild=after,
                log_location="guild",
                string_message=console_message,
                embed_message=embed,
            )

    @commands.Cog.listener()
    async def on_thread_create(self: Self, thread: discord.Thread) -> None:
        """This logs events related to creating a new thread
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_thread_create

        Args:
            thread (discord.Thread): The thread object that was created
        """
        embed = EventEmbed(
            title="Thread created",
            description="",
        )

        embed.addChannelField("Thread", thread)
        embed.addChannelField("Parent channel", thread.parent)

        console_message = f"Thread {thread.name} ({thread.id}) was created"

        await self.send_event_log(
            guild=thread.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
            channel_location=thread.parent,
        )

    @commands.Cog.listener()
    async def on_thread_delete(self: Self, thread: discord.Thread) -> None:
        """This logs events related to deleting a thread
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_thread_delete

        Args:
            thread (discord.Thread): The thread object that was deleted
        """
        embed = EventEmbed(
            title="Thread deleted",
            description="",
        )

        embed.addChannelField("Thread", thread)
        embed.addChannelField("Parent channel", thread.parent)

        console_message = f"Thread {thread.name} ({thread.id}) was deleted"

        await self.send_event_log(
            guild=thread.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
            channel_location=thread.parent,
        )

    @commands.Cog.listener()
    async def on_thread_update(
        self: Self, before: discord.Thread, after: discord.Thread
    ) -> None:
        """This logs changes related to a handful of properties of threads
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_thread_update

        Args:
            before (discord.Thread): The previous thread, before any property changes
            after (discord.Thread): The new thread, after any property changes
        """
        properties_to_track = [
            "applied_tags",
            "archived",
            "invitable",
            "locked",
            "name",
            "slowmode_delay",
            "type",
        ]
        embed = EventEmbed(title="Thread properties updated", description="")
        embed.addChannelField("Thread", after)
        embed.addChannelField("Parent channel", after.parent)

        if embed.addPropertyChangeFields(properties_to_track, before, after):
            console_message = (
                f"Thread properties updated for thread " f"{after.name} ({after.id})"
            )

            await self.send_event_log(
                guild=after.guild,
                log_location="guild",
                string_message=console_message,
                embed_message=embed,
                channel_location=after,
            )

    @commands.Cog.listener()
    async def on_invite_create(self: Self, invite: discord.Invite) -> None:
        """This logs events related to creating a new invite for the guild
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_thread_update

        Args:
            invite (discord.Invite): The invite that was created.
        """
        embed = EventEmbed(
            title="New invite created", description=f"https://discord.gg/{invite.code}"
        )
        if invite.channel:
            embed.addChannelField("Channel", invite.channel)
        if invite.inviter:
            embed.addMemberField("Inviter", invite.inviter)

        console_message = f"New invite created: {invite.code}"

        await self.send_event_log(
            guild=invite.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
            channel_location=invite.channel,
        )

    @commands.Cog.listener()
    async def on_invite_delete(self: Self, invite: discord.Invite) -> None:
        """This logs events related to deleting an invite for the guild
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_thread_update

        Args:
            invite (discord.Invite): The invite that was deleted.
        """
        embed = EventEmbed(
            title="Invite deleted", description=f"https://discord.gg/{invite.code}"
        )
        if invite.channel:
            embed.addChannelField("Channel", invite.channel)
        if invite.inviter:
            embed.addMemberField("Inviter", invite.inviter)

        console_message = f"Invite deleted: {invite.code}"

        await self.send_event_log(
            guild=invite.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
            channel_location=invite.channel,
        )

    @commands.Cog.listener()
    async def on_soundboard_sound_create(
        self: Self, sound: discord.SoundboardSound
    ) -> None:
        """This logs events related to a new soundboard sound being created
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_soundboard_sound_create

        Args:
            sound (discord.SoundboardSound): The soundboard object that was created
        """
        embed = EventEmbed(title="Soundboard sound created", description="")
        embed.addSoundboardField("Sound", sound)
        if sound.user:
            embed.addMemberField("Uploader", sound.user)

        console_message = f"Soundboard sound created: {sound.name}"

        await self.send_event_log(
            guild=sound.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_soundboard_sound_delete(
        self: Self, sound: discord.SoundboardSound
    ) -> None:
        """This logs events related to a new soundboard sound being deleted
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_soundboard_sound_delete

        Args:
            sound (discord.SoundboardSound): The soundboard object that was deleted
        """
        embed = EventEmbed(title="Soundboard sound deleted", description="")
        embed.addSoundboardField("Sound", sound)
        if sound.user:
            embed.addMemberField("Uploader", sound.user)

        console_message = f"Soundboard sound deleted: {sound.name}"

        await self.send_event_log(
            guild=sound.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_soundboard_sound_update(
        self: Self, before: discord.SoundboardSound, after: discord.SoundboardSound
    ) -> None:
        """This logs events related to soundboard sounds being edited
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_soundboard_sound_update

        Args:
            before (discord.SoundboardSound): The old sound, before any edits
            after (discord.SoundboardSound): The new sound, after any edits
        """
        embed = EventEmbed(title="Soundboard sound modified", description="")
        embed.addSoundboardField("Sound", after)
        if after.user:
            embed.addMemberField("Uploader", after.user)

        properties_to_track = [
            "available",
            "emoji",
            "name",
            "volume",
        ]
        if embed.addPropertyChangeFields(properties_to_track, before, after):
            console_message = f"Soundboard sound modified: {after.name}"
            await self.send_event_log(
                guild=after.guild,
                log_location="guild",
                string_message=console_message,
                embed_message=embed,
            )

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self: Self,
        guild: discord.Guild,
        before: Sequence[discord.Emoji],
        after: Sequence[discord.Emoji],
    ) -> None:
        """This logs events related to custom emojis in guilds being created, deleted or edited.
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_emojis_update

        Args:
            guild (discord.Guild): The guild these changes occured in
            before (Sequence[discord.Emoji]): The list of guild emojis before any changes
            after (Sequence[discord.Emoji]): The list of guild emojis after any changes
        """
        before_emojis = {emoji.id: emoji for emoji in before}
        after_emojis = {emoji.id: emoji for emoji in after}

        # Created emojis
        for emoji_id, emoji in after_emojis.items():
            if emoji_id not in before_emojis:
                embed = EventEmbed(title="Emoji created", description="")
                embed.addEmojiField("Emoji", emoji)
                if emoji.user:
                    embed.addMemberField("Uploader", emoji.user)

                console_message = f"Emoji created: {emoji.name}"

                await self.send_event_log(
                    guild=guild,
                    log_location="guild",
                    string_message=console_message,
                    embed_message=embed,
                )

        # Deleted emojis
        for emoji_id, emoji in before_emojis.items():
            if emoji_id not in after_emojis:
                embed = EventEmbed(title="Emoji deleted", description="")
                embed.addEmojiField("Emoji", emoji)
                if emoji.user:
                    embed.addMemberField("Uploader", emoji.user)

                console_message = f"Emoji deleted: {emoji.name}"

                await self.send_event_log(
                    guild=guild,
                    log_location="guild",
                    string_message=console_message,
                    embed_message=embed,
                )

        # Modified emojis
        # I honestly don't think this is possible to hit
        properties_to_track = [
            "animated",
            "name",
        ]

        for emoji_id, after_emoji in after_emojis.items():
            before_emoji = before_emojis.get(emoji_id)

            if before_emoji is None:
                continue

            embed = EventEmbed(title="Emoji modified", description="")
            embed.addEmojiField("Emoji", after_emoji)
            if after_emoji.user:
                embed.addMemberField("Uploader", after_emoji.user)

            if embed.addPropertyChangeFields(
                properties_to_track,
                before_emoji,
                after_emoji,
            ):
                console_message = f"Emoji modified: {after_emoji.name}"

                await self.send_event_log(
                    guild=guild,
                    log_location="guild",
                    string_message=console_message,
                    embed_message=embed,
                )

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self: Self,
        guild: discord.Guild,
        before: Sequence[discord.GuildSticker],
        after: Sequence[discord.GuildSticker],
    ) -> None:
        """This logs events related to custom stickers in guilds being created, deleted or edited.
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_stickers_update

        Args:
            guild (discord.Guild): The guild these changes occured in
            before (Sequence[discord.GuildSticker]): The list of guild stickers before any changes
            after (Sequence[discord.GuildSticker]): The list of guild stickers after any changes
        """
        before_stickers = {sticker.id: sticker for sticker in before}
        after_stickers = {sticker.id: sticker for sticker in after}

        # Created stickers
        for sticker_id, sticker in after_stickers.items():
            if sticker_id not in before_stickers:
                embed = EventEmbed(title="Sticker created", description="")
                embed.addStickerField("Sticker", sticker)
                if sticker.user:
                    embed.addMemberField("Uploader", sticker.user)

                console_message = f"Sticker created: {sticker.name}"

                await self.send_event_log(
                    guild=guild,
                    log_location="guild",
                    string_message=console_message,
                    embed_message=embed,
                )

        # Deleted stickers
        for sticker_id, sticker in before_stickers.items():
            if sticker_id not in after_stickers:
                embed = EventEmbed(title="Sticker deleted", description="")
                embed.addStickerField("Sticker", sticker)
                if sticker.user:
                    embed.addMemberField("Uploader", sticker.user)

                console_message = f"Sticker deleted: {sticker.name}"

                await self.send_event_log(
                    guild=guild,
                    log_location="guild",
                    string_message=console_message,
                    embed_message=embed,
                )

        # Modified stickers
        properties_to_track = [
            "description",
            "emoji",
            "name",
        ]

        for sticker_id, after_sticker in after_stickers.items():
            before_sticker = before_stickers.get(sticker_id)

            if before_sticker is None:
                continue

            embed = EventEmbed(title="Sticker modified", description="")
            embed.addStickerField("Sticker", after_sticker)
            if after_sticker.user:
                embed.addMemberField("Uploader", after_sticker.user)

            if embed.addPropertyChangeFields(
                properties_to_track,
                before_sticker,
                after_sticker,
            ):
                console_message = f"Sticker modified: {after_sticker.name}"

                await self.send_event_log(
                    guild=guild,
                    log_location="guild",
                    string_message=console_message,
                    embed_message=embed,
                )

    @commands.Cog.listener()
    async def on_integration_create(
        self: Self, integration: discord.Integration
    ) -> None:
        """This logs events related to new integrations being added in the guild
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_integration_create

        Args:
            integration (discord.Integration): The integration that was created
        """
        embed = EventEmbed(title="Integration created", description="")
        embed.addMemberField("Bot user", integration.account)
        embed.addMemberField("Uploader", integration.user)
        embed.addIntegrationField("Integration info", integration)

        console_message = f"Integration created: {integration.name} ({integration.id})"

        await self.send_event_log(
            guild=integration.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_raw_integration_delete(
        self: Self, payload: discord.RawIntegrationDeleteEvent
    ) -> None:
        """This logs events related to new integrations being removed from the guild
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_integration_delete

        Args:
            payload (discord.RawIntegrationDeleteEvent): The integration that was deleted
        """
        guild = await self.bot.fetch_guild(payload.guild_id)
        embed = EventEmbed(
            title="Integration deleted",
            description=f"Integration ID: {payload.integration_id}",
        )

        console_message = f"Integration deleted: ({payload.integration_id})"

        await self.send_event_log(
            guild=guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_scheduled_event_create(
        self: Self, event: discord.ScheduledEvent
    ) -> None:
        """Logs events related to creating new scheduled events in a guild
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_scheduled_event_create

        Args:
            event (discord.ScheduledEvent): The event that has been created
        """
        embed = EventEmbed(title="Scheduled event created", description=event.url)
        embed.addScheduledEventField("Scheduled Event", event)
        if event.creator:
            embed.addMemberField("Creator", event.creator)

        console_message = f"Scheduled event created: {event.name} ({event.id})"

        await self.send_event_log(
            guild=event.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
            channel_location=event.channel,
        )

    @commands.Cog.listener()
    async def on_scheduled_event_delete(
        self: Self, event: discord.ScheduledEvent
    ) -> None:
        """Logs events related to deleting scheduled events in a guild
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_scheduled_event_delete

        Args:
            event (discord.ScheduledEvent): The event that has been deleted
        """
        embed = EventEmbed(title="Scheduled event deleted", description=event.url)
        embed.addScheduledEventField("Scheduled Event", event)
        if event.creator:
            embed.addMemberField("Creator", event.creator)

        console_message = f"Scheduled event deleted: {event.name} ({event.id})"

        await self.send_event_log(
            guild=event.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
            channel_location=event.channel,
        )

    @commands.Cog.listener()
    async def on_scheduled_event_update(
        self: Self,
        before: discord.ScheduledEvent,
        after: discord.ScheduledEvent,
    ) -> None:
        """This logs events related to scheduled events being edited
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_scheduled_event_update

        Args:
            before (discord.ScheduledEvent): The original event, before any edits
            after (discord.ScheduledEvent): The new event, after any edits
        """
        properties_to_track = [
            "channel_id",
            "description",
            "end_time",
            "entity_type",
            "location",
            "name",
            "privacy_level",
            "start_time",
            "status",
        ]
        embed = EventEmbed(title="Scheduled event updated", description=after.url)
        embed.addScheduledEventField("Scheduled Event", after)

        if embed.addPropertyChangeFields(properties_to_track, before, after):
            console_message = f"Scheduled event updated: {after.name} ({after.id})"

            await self.send_event_log(
                guild=after.guild,
                log_location="guild",
                string_message=console_message,
                embed_message=embed,
                channel_location=after.channel,
            )

    @commands.Cog.listener()
    async def on_guild_role_create(self: Self, role: discord.Role) -> None:
        """This logs events related to creating new roles
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_create

        Args:
            role (discord.Role): The role object that was created
        """
        embed = EventEmbed(title="Role created", description="")
        embed.addRoleField("Role", role)
        embed.addRoleMetadataField("Role Metadata", role)
        embed.addRoleColorField("Role Colors", role)

        console_message = f"Role created: {role.name} ({role.id})"

        await self.send_event_log(
            guild=role.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self: Self, role: discord.Role) -> None:
        """This logs events related to deleting roles
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_delete

        Args:
            role (discord.Role): The role object that was deleted
        """
        embed = EventEmbed(title="Role deleted", description="")
        embed.addRoleField("Role", role)
        embed.addRoleMetadataField("Role Metadata", role)
        embed.addRoleColorField("Role Colors", role)

        console_message = f"Role deleted: {role.name} ({role.id})"

        await self.send_event_log(
            guild=role.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_guild_role_update(
        self: Self, before: discord.Role, after: discord.Role
    ) -> None:
        """This logs events related to updating a role. 3 different logs are generated here:
        Role color changes
        Role permission changes
        Other role property changes
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_update

        Args:
            before (discord.Role): The old role, before any changes
            after (discord.Role): The new role, after any changes
        """
        general_properties_to_track = [
            "display_icon",
            "flags",
            "hoist",
            "icon",
            "managed",
            "mentionable",
            "name",
            "position",
            "tags",
            "unicode_emoji",
        ]

        general_embed = EventEmbed(title="Role properties updated", description="")
        general_embed.addRoleField("Role", after)

        if general_embed.addPropertyChangeFields(
            general_properties_to_track, before, after
        ):
            console_message = f"Role properties updated: {after.name} ({after.id})"

            await self.send_event_log(
                guild=after.guild,
                log_location="guild",
                string_message=console_message,
                embed_message=general_embed,
            )

        permission_embed = EventEmbed(title="Role permissions updated", description="")
        permission_embed.addRoleField("Role", after)

        if permission_embed.addRolePermissionChangeFields(
            before.permissions, after.permissions
        ):
            console_message = f"Role permissions updated: {after.name} ({after.id})"

            await self.send_event_log(
                guild=after.guild,
                log_location="guild",
                string_message=console_message,
                embed_message=permission_embed,
            )

        color_properties_to_track = [
            "colour",
            "secondary_colour",
            "tertiary_colour",
        ]
        color_embed = EventEmbed(title="Role colors updated", description="")
        color_embed.addRoleField("Role", after)
        color_embed.addRoleColorField("Role Colors", after)

        if color_embed.addPropertyChangeFields(
            color_properties_to_track, before, after
        ):
            console_message = f"Role colors updated: {after.name} ({after.id})"

            await self.send_event_log(
                guild=after.guild,
                log_location="guild",
                string_message=console_message,
                embed_message=color_embed,
            )

    @commands.Cog.listener()
    async def on_automod_rule_create(self: Self, rule: discord.AutoModRule) -> None:
        """This logs events related to creating a new automod rule
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_automod_rule_create

        Args:
            rule (discord.AutoModRule): The automod rule that was created
        """
        embed = EventEmbed(title="AutoMod rule created", description="")
        embed.addAutoModRuleField("AutoMod Rule", rule)
        if rule.creator:
            embed.addMemberField("Creator", rule.creator)

        console_message = f"AutoMod rule created: {rule.name} ({rule.id})"

        await self.send_event_log(
            guild=rule.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_automod_rule_update(self: Self, rule: discord.AutoModRule) -> None:
        """This logs events related to updating an automod rule
        As discord does not give the old rule before edits, we cannot log what has changed.
            Only that something has changed.
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_automod_rule_update

        Args:
            rule (discord.AutoModRule): The automod rule that was updated
        """
        embed = EventEmbed(title="AutoMod rule updated", description="")
        embed.addAutoModRuleField("AutoMod Rule", rule)
        if rule.creator:
            embed.addMemberField("Creator", rule.creator)

        console_message = f"AutoMod rule updated: {rule.name} ({rule.id})"

        await self.send_event_log(
            guild=rule.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    @commands.Cog.listener()
    async def on_automod_rule_delete(self: Self, rule: discord.AutoModRule) -> None:
        """This logs events related to deleting an automod rule
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_automod_rule_delete

        Args:
            rule (discord.AutoModRule): The automod rule that was deleted
        """
        embed = EventEmbed(title="AutoMod rule deleted", description="")
        embed.addAutoModRuleField("AutoMod Rule", rule)
        if rule.creator:
            embed.addMemberField("Creator", rule.creator)

        console_message = f"AutoMod rule deleted: {rule.name} ({rule.id})"

        await self.send_event_log(
            guild=rule.guild,
            log_location="guild",
            string_message=console_message,
            embed_message=embed,
        )

    # Bot Events

    @commands.Cog.listener()
    async def on_command(self: Self, ctx: commands.Context) -> None:
        """
        See:
        https://discordpy.readthedocs.io/en/stable/ext/commands/
        api.html#discord.discord.ext.commands.on_command

        Args:
            ctx (commands.Context): The invocation context
        """
        embed = discord.Embed()
        embed.add_field(name="User", value=ctx.author)
        embed.add_field(name="Channel", value=getattr(ctx.channel, "name", "DM"))
        embed.add_field(name="Server", value=getattr(ctx.guild, "name", "None"))

        log_channel = configuration.get_config_entry(
            ctx.guild.id, "core_logging_channel"
        )

        sliced_content = ctx.message.content[:100]
        message = f"Command detected: {sliced_content}"

        await self.bot.logger.send_log(
            message=message,
            level=LogLevel.INFO,
            context=LogContext(guild=ctx.guild, channel=ctx.channel),
            channel=log_channel,
            embed=embed,
        )
