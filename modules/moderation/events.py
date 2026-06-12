"""All of the discord event listeners where they used for logging"""

from __future__ import annotations

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
    """This subclass of embed contains several functions to create consistent fields for displaying various types of data in the event logs"""

    def __init__(self, *, title, description) -> None:
        super().__init__(
            title=title,
            description=description,
            colour=discord.Colour.orange(),
            timestamp=discord.utils.utcnow(),
        )

    def setEventAuthor(self, author: discord.Member) -> None:
        self.set_author(
            name=str(author.display_name),
            icon_url=author.display_avatar.url,
        )

    def addMemberField(self: Self, title: str, member: discord.Member) -> None:
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

    def addEmojiField(
        self: Self, title: str, emoji: discord.Emoji | discord.PartialEmoji | str
    ) -> None:
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

    def addPollField(self: Self, title: str, poll: discord.Poll) -> None:
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
        self.add_field(
            name=title,
            value=(f"**Answer:** {answer.text}\n**ID:** {answer.id}"),
            inline=True,
        )

    def addPropertyChangeFields(
        self: Self, properties: list[str], before: Any, after: Any
    ) -> bool:
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
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_edit

        Args:
            payload (discord.RawMessageUpdateEvent): The raw payload object for the message edit events
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

            console_message = f"Message edit: ID: {after.id} in channel: {after.channel.name} ({after.channel.id}). Old: {old_content}, new {after.clean_content}"

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

            console_message = f"Message pins changed: ID: {after.id} in channel: {after.channel.name} ({after.channel.id}). Pinned status: {after.pinned}"

            await self.send_event_log(
                guild=after.guild,
                log_location="message",
                string_message=console_message,
                embed_message=embed,
                channel_location=after.channel,
            )

    @commands.Cog.listener()
    async def on_message_delete(self: Self, message: discord.Message) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_delete

        Args:
            message (discord.Message): The deleted message
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

        console_message = f"Message delete: ID: {message.id} in channel: {channel.name} ({channel.id}). Content: {message.clean_content}"

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
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_bulk_message_delete

        Args:
            messages (list[discord.Message]): The messages that have been deleted
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

        console_message = f"Bulk message delete: Channel: {channel.name} ({channel.id}). Amount: {len(messages)}"

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
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_add

        Args:
            reaction (discord.Reaction): The current state of the reaction
            user (discord.Member | discord.User): The user who added the reaction
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

        console_message = f"Reaction {reaction.emoji} added to message with ID: {message.id} by user {user.name} ({user.id})"

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
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_remove

        Args:
            reaction (discord.Reaction): The current state of the reaction
            user (discord.Member | discord.User): The user whose reaction was removed
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

        console_message = f"Reaction {reaction.emoji} removed from message with ID: {message.id} by user {user.name} ({user.id})"

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
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_clear

        Args:
            message (discord.Message): The message that had its reactions cleared
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

        console_message = f"{total_emoji} reactions cleared from message with ID: {message.id} in channel {channel.name} ({channel.id})"

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

        console_message = f"User {user.name} ({user.id}) voted {answer.text} to poll message {message.id} in channel {channel.name} ({channel.id})"

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

        console_message = f"User {user.name} ({user.id}) removed vote {answer.text} from a poll message {message.id} in channel {channel.name} ({channel.id})"

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
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join

        Args:
            member (discord.Member): The member who joined
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
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_remove

        Args:
            member (discord.Member): The member who left
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
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_update

        Args:
            before (discord.Member): The updated member's old info
            after (discord.Member): Teh updated member's new info
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

            console_message = f"Member roles updated: {after.name} ({after.id}). Roles changed {', '.join(role.name for role in changed_role)}"

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
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_create

        Args:
            channel (discord.abc.GuildChannel): The channel that got created
        """

        embed = EventEmbed(
            title="Channel created",
            description=f"",
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
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_delete

        Args:
            channel (discord.abc.GuildChannel): The channel that got deleted
        """
        embed = EventEmbed(
            title="Channel deleted",
            description=f"",
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
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_update

        Args:
            before (discord.abc.GuildChannel): The updated guild channel's old info
            after (discord.abc.GuildChannel): The updated guild channel's new info
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
                    target_name = f"Role:"
                    value_parts.append(f"{target.mention}")
                elif isinstance(target, discord.Member):
                    target_name = f"Member:"
                    value_parts.append(f"{target.mention}")
                else:
                    target_name = f"Unknown:"
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
                f"Permission overwrites updated for channel "
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
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_update

        Args:
            before (discord.Guild): The guild prior to being updated
            after (discord.Guild): The guild after being updated
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
            console_message = f"Guild properties updated."

            await self.send_event_log(
                guild=after,
                log_location="guild",
                string_message=console_message,
                embed_message=embed,
            )

    @commands.Cog.listener()
    async def on_thread_create(self: Self, thread: discord.Thread) -> None:
        embed = EventEmbed(
            title="Thread created",
            description=f"",
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
        embed = EventEmbed(
            title="Thread deleted",
            description=f"",
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


# Should probably log:
"""
    @commands.Cog.listener()
    async def on(self: Self) -> None:

Soundboard, stickers & emoji (guild)
    discord.on_soundboard_sound_create
    discord.on_soundboard_sound_delete
    discord.on_soundboard_sound_update
    discord.on_guild_stickers_update
    discord.on_guild_emojis_update
Integrations (guild)
    discord.on_integration_create
    discord.on_raw_integration_delete
Scheduled Events (guild)
    discord.on_scheduled_event_create
    discord.on_scheduled_event_delete
    discord.on_scheduled_event_update
Roles (guild)
    discord.on_guild_role_create
    discord.on_guild_role_delete
    discord.on_guild_role_update
Automod stuff (guild)
    discord.on_automod_rule_create
    discord.on_automod_rule_update
    discord.on_automod_rule_delete
"""
