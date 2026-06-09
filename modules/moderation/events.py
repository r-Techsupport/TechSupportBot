"""All of the discord event listeners where they used for logging"""

from __future__ import annotations

import datetime
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING, Self

import discord
from discord.ext import commands

import configuration
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Event Logging plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(EventLogger(bot=bot))


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

    # MESSAGE EVENTS

    @commands.Cog.listener()
    async def on_raw_message_edit(
        self: Self, payload: discord.RawMessageUpdateEvent
    ) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_message_edit

        Args:
            payload (discord.RawMessageUpdateEvent): The raw payload object for the message edit events
        """
        before = payload.cached_message
        after = payload.message

        # Ignore message edit events for not content changes
        if before and before.content == after.content:
            return

        guild = getattr(after.channel, "guild", None)

        # Ignore all message edit events in DMs
        if not guild:
            return

        # Ignore ephemeral slash command messages
        if after.type == discord.MessageType.chat_input_command:
            return

        embed = discord.Embed(
            title="Message Edited",
            description=f"[Jump to Message]({after.jump_url})",
            colour=discord.Colour.orange(),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_author(
            name=str(after.author),
            icon_url=after.author.display_avatar.url,
        )

        embed.add_field(
            name="Author",
            value=(
                f"**User:** {after.author.mention}\n"
                f"**Name:** {after.author}\n"
                f"**ID:** {after.author.id}"
            ),
            inline=True,
        )

        embed.add_field(
            name="Channel",
            value=(
                f"**Channel:** {after.channel.mention}\n"
                f"**Name:** #{after.channel.name}\n"
                f"**ID:** {after.channel.id}"
            ),
            inline=True,
        )

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
        if before:
            old_content = before.clean_content
            embed.add_field(
                name="Original Content",
                value=before.content[:1024] if before.content else "*No content*",
                inline=False,
            )
        else:
            old_content = "**Unknown. Perhaps this message was too old?**"
            embed.add_field(
                name="Original Content",
                value=old_content,
                inline=False,
            )

        embed.add_field(
            name="New Content",
            value=after.content[:1024] if after.content else "*No content*",
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

        embed = discord.Embed(
            title="Message Deleted",
            description=f"[Jump to Message]({message.jump_url})",
            colour=discord.Colour.orange(),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_author(
            name=str(message.author),
            icon_url=message.author.display_avatar.url,
        )

        embed.add_field(
            name="Author",
            value=(
                f"**User:** {message.author.mention}\n"
                f"**Name:** {message.author}\n"
                f"**ID:** {message.author.id}"
            ),
            inline=True,
        )

        embed.add_field(
            name="Channel",
            value=(
                f"**Channel:** {channel.mention}\n"
                f"**Name:** #{channel.name}\n"
                f"**ID:** {channel.id}"
            ),
            inline=True,
        )

        embed.add_field(
            name="Timestamps",
            value=(
                f"**Sent:** <t:{int(message.created_at.timestamp())}:F> "
                f"(<t:{int(message.created_at.timestamp())}:R>)\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="Message Content",
            value=message.content[:1024] if message.content else "*No content*",
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

        embed = discord.Embed()

        embed = discord.Embed(
            title="Bulk Message Delete",
            colour=discord.Colour.orange(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="Channel",
            value=(
                f"**Channel:** {channel.mention}\n"
                f"**Name:** #{channel.name}\n"
                f"**ID:** {channel.id}"
            ),
            inline=True,
        )

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
        guild = getattr(reaction.message.channel, "guild", None)

        if isinstance(reaction.message.channel, discord.DMChannel):
            await self.bot.logger.send_log(
                message=(
                    f"PM from `{user}`: added {reaction.emoji} reaction to message"
                    f" {reaction.message.content} in DMs"
                ),
                level=LogLevel.INFO,
            )
            return

        embed = discord.Embed()
        embed.add_field(name="Emoji", value=reaction.emoji)
        embed.add_field(name="User", value=user)
        embed.add_field(name="Message", value=reaction.message.content or "None")
        embed.add_field(name="Message Author", value=reaction.message.author)
        embed.add_field(
            name="Channel", value=getattr(reaction.message.channel, "name", "DM")
        )
        embed.add_field(name="Server", value=guild.name)

        log_channel = configuration.get_config_entry(
            guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"Reaction added to message with ID {reaction.message.id} by user with"
                f" ID {user.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(
                guild=reaction.message.channel.guild, channel=reaction.message.channel
            ),
            channel=log_channel,
            embed=embed,
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
        guild = getattr(reaction.message.channel, "guild", None)

        if isinstance(reaction.message.channel, discord.DMChannel):
            await self.bot.logger.send_log(
                message=(
                    f"PM from `{user}`: removed {reaction.emoji} reaction to message"
                    f" {reaction.message.content} in DMs"
                ),
                level=LogLevel.INFO,
            )
            return

        embed = discord.Embed()
        embed.add_field(name="Emoji", value=reaction.emoji)
        embed.add_field(name="User", value=user)
        embed.add_field(name="Message", value=reaction.message.content or "None")
        embed.add_field(name="Message Author", value=reaction.message.author)
        embed.add_field(
            name="Channel", value=getattr(reaction.message.channel, "name", "DM")
        )
        embed.add_field(name="Server", value=guild.name)

        log_channel = configuration.get_config_entry(
            guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"Reaction removed from message with ID {reaction.message.id} by user"
                f" with ID {user.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(
                guild=reaction.message.channel.guild, channel=reaction.message.channel
            ),
            channel=log_channel,
            embed=embed,
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

        unique_emojis = set()
        for reaction in reactions:
            unique_emojis.add(reaction.emoji)

        embed = discord.Embed()
        embed.add_field(name="Emojis", value=",".join(unique_emojis))
        embed.add_field(name="Message", value=message.content or "None")
        embed.add_field(name="Message Author", value=message.author)
        embed.add_field(name="Channel", value=getattr(message.channel, "name", "DM"))
        embed.add_field(name="Server", value=guild.name)

        log_channel = configuration.get_config_entry(
            guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"{len(reactions)} cleared from message with ID {message.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=message.channel.guild, channel=message.channel),
            channel=log_channel,
            embed=embed,
        )

    # Guild Events

    @commands.Cog.listener()
    async def on_guild_channel_delete(
        self: Self, channel: discord.abc.GuildChannel
    ) -> None:
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_delete

        Args:
            channel (discord.abc.GuildChannel): The channel that got deleted
        """
        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild.name)

        log_channel = configuration.get_config_entry(
            channel.guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"Channel with ID {channel.id} deleted in guild with ID"
                f" {channel.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=channel.guild, channel=channel),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_channel_create(
        self: Self, channel: discord.abc.GuildChannel
    ) -> None:
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_create

        Args:
            channel (discord.abc.GuildChannel): The channel that got created
        """
        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild.name)
        log_channel = configuration.get_config_entry(
            channel.guild.id, "core_guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=(
                f"Channel with ID {channel.id} created in guild with ID"
                f" {channel.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=channel.guild, channel=channel),
            channel=log_channel,
            embed=embed,
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
        attrs = [
            "category",
            "changed_roles",
            "name",
            "overwrites",
            "permissions_synced",
            "position",
        ]
        diff = auxiliary.get_object_diff(before, after, attrs)

        embed = discord.Embed()
        embed = auxiliary.add_diff_fields(embed, diff)
        embed.add_field(name="Channel Name", value=before.name)
        embed.add_field(name="Server", value=before.guild.name)

        log_channel = configuration.get_config_entry(
            before.guild.id, "core_guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=(
                f"Channel with ID {before.id} modified in guild with ID"
                f" {before.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=before.guild, channel=before),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(
        self: Self,
        channel: discord.abc.GuildChannel | discord.Thread,
        _last_pin: datetime.datetime | None,
    ) -> None:
        """
        See:
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_pins_update

        Args:
            channel (discord.abc.GuildChannel | discord.Thread): The guild channel
                that had its pins updated.
            _last_pin (datetime.datetime | None): The latest message that was pinned as an
                aware datetime in UTC. Could be None.
        """
        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild)

        log_channel = configuration.get_config_entry(
            channel.guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"Channel pins updated in channel with ID {channel.id} in guild with ID"
                f" {channel.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=channel.guild, channel=channel),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_integrations_update(self: Self, guild: discord.Guild) -> None:
        """
        See:
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_integrations_update

        Args:
            guild (discord.Guild): The guild that had its integrations updated.
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild)
        log_channel = configuration.get_config_entry(
            guild.id, "core_guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=f"Integrations updated in guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_webhooks_update(self: Self, channel: discord.abc.GuildChannel) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_webhooks_update

        Args:
            channel (discord.abc.GuildChannel): The channel that had its webhooks updated.
        """
        embed = discord.Embed()
        embed.add_field(name="Channel", value=channel.name)
        embed.add_field(name="Server", value=channel.guild)

        log_channel = configuration.get_config_entry(
            channel.guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"Webooks updated for channel with ID {channel.id} in guild with ID"
                f" {channel.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=channel.guild, channel=channel),
            channel=log_channel,
            embed=embed,
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
        diff = auxiliary.get_object_diff(
            before,
            after,
            [
                "banner",
                "banner_url",
                "bitrate_limit",
                "categories",
                "default_role",
                "description",
                "discovery_splash",
                "discovery_splash_url",
                "emoji_limit",
                "emojis",
                "explicit_content_filter",
                "features",
                "icon",
                "icon_url",
                "name",
                "owner",
                "region",
                "roles",
                "rules_channel",
                "verification_level",
            ],
        )

        embed = discord.Embed()
        embed = auxiliary.add_diff_fields(embed, diff)
        embed.add_field(name="Server", value=before.name)

        log_channel = configuration.get_config_entry(
            before.guild.id, "core_guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=f"Guild with ID {before.id} updated",
            level=LogLevel.INFO,
            context=LogContext(guild=before),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self: Self, role: discord.Role) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_create

        Args:
            role (discord.Role): The role that was created
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=role.guild.name)
        log_channel = configuration.get_config_entry(
            role.guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"New role with name {role.name} added to guild with ID {role.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=role.guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self: Self, role: discord.Role) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_delete

        Args:
            role (discord.Role): The role that was deleted
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=role.guild.name)
        log_channel = configuration.get_config_entry(
            role.guild.id, "core_guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=(
                f"Role with name {role.name} deleted from guild with ID {role.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=role.guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_role_update(
        self: Self, before: discord.Role, after: discord.Role
    ) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_update

        Args:
            before (discord.Role): The updated role's old info.
            after (discord.Role): The updated role's updated info.
        """
        attrs = ["color", "mentionable", "name", "permissions", "position", "tags"]
        diff = auxiliary.get_object_diff(before, after, attrs)

        embed = discord.Embed()
        embed = auxiliary.add_diff_fields(embed, diff)
        embed.add_field(name="Server", value=before.name)

        log_channel = configuration.get_config_entry(
            before.guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"Role with name {before.name} updated in guild with ID"
                f" {before.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=before.guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self: Self,
        guild: discord.Guild,
        _: Sequence[discord.Emoji],
        __: Sequence[discord.Emoji],
    ) -> None:
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_emojis_update

        Args:
            guild (discord.Guild): The guild who got their emojis updated.
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild.name)

        log_channel = configuration.get_config_entry(
            guild.id, "core_guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=f"Emojis updated in guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )

    # Member Events

    @commands.Cog.listener()
    async def on_member_update(
        self: Self, before: discord.Member, after: discord.Member
    ) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_update

        Args:
            before (discord.Member): The updated member's old info
            after (discord.Member): Teh updated member's new info
        """
        changed_role = set(before.roles) ^ set(after.roles)
        if changed_role:
            if len(before.roles) < len(after.roles):
                embed = discord.Embed()
                embed.add_field(name="Roles added", value=next(iter(changed_role)))
                embed.add_field(name="Server", value=before.guild.name)
            else:
                embed = discord.Embed()
                embed.add_field(name="Roles lost", value=next(iter(changed_role)))
                embed.add_field(name="Server", value=before.guild.name)

            log_channel = configuration.get_config_entry(
                before.guild.id, "core_member_events_channel"
            )

            await self.bot.logger.send_log(
                message=(
                    f"Member with ID {before.id} has changed status in guild with ID"
                    f" {before.guild.id}"
                ),
                level=LogLevel.INFO,
                context=LogContext(guild=before.guild),
                channel=log_channel,
                embed=embed,
            )

    @commands.Cog.listener()
    async def on_member_remove(self: Self, member: discord.Member) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_remove

        Args:
            member (discord.Member): The member who left
        """
        embed = discord.Embed()
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Server", value=member.guild.name)
        log_channel = configuration.get_config_entry(
            member.guild.id, "core_member_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"Member with ID {member.id} has left guild with ID {member.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=member.guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_member_ban(
        self: Self, guild: discord.Guild, user: discord.User | discord.Member
    ) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_ban

        Args:
            guild (discord.Guild): The guild the user got banned from
            user (discord.User | discord.Member): The user that got banned. Can be either User
                or Member depending if the user was in the guild or not at the time of removal.
        """
        embed = discord.Embed()
        embed.add_field(name="User", value=user)
        embed.add_field(name="Server", value=guild.name)

        log_channel = configuration.get_config_entry(
            guild.id, "core_member_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"User with ID {user.id} banned from guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_member_unban(
        self: Self, guild: discord.Guild, user: discord.User
    ) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_unban

        Args:
            guild (discord.Guild): The guild the user got unbanned from
            user (discord.User): The user that got unbanned
        """
        embed = discord.Embed()
        embed.add_field(name="User", value=user)
        embed.add_field(name="Server", value=guild.name)

        log_channel = configuration.get_config_entry(
            guild.id, "core_member_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"User with ID {user.id} unbanned from guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_member_join(self: Self, member: discord.Member) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join

        Args:
            member (discord.Member): The member who joined
        """
        embed = discord.Embed()
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Server", value=member.guild.name)
        log_channel = configuration.get_config_entry(
            member.guild.id, "core_member_events_channel"
        )

        await self.bot.logger.send_log(
            message=(
                f"Member with ID {member.id} has joined guild with ID {member.guild.id}"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=member.guild),
            channel=log_channel,
            embed=embed,
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

    # CONSOLE ONLY STUFF

    @commands.Cog.listener()
    async def on_error(self: Self, event_method: str) -> None:
        """Catches non-command errors and sends them to the error logger for processing.

        Args:
            event_method (str): the event method name associated with the error (eg. on_message)
        """
        _, exception, _ = sys.exc_info()
        await self.bot.logger.send_log(
            message=f"Bot error in {event_method}: {exception}",
            level=LogLevel.ERROR,
            exception=exception,
        )

    @commands.Cog.listener()
    async def on_connect(self: Self) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_connect"""
        await self.bot.logger.send_log(
            message="Connected to Discord",
            level=LogLevel.INFO,
            console_only=True,
        )

    @commands.Cog.listener()
    async def on_resumed(self: Self) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_resumed"""
        await self.bot.logger.send_log(
            message="Resume event",
            level=LogLevel.INFO,
            console_only=True,
        )

    @commands.Cog.listener()
    async def on_disconnect(self: Self) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_disconnect"""
        await self.bot.logger.send_log(
            message="Disconnected from Discord",
            level=LogLevel.INFO,
            console_only=True,
        )

    @commands.Cog.listener()
    async def on_guild_remove(self: Self, guild: discord.Guild) -> None:
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_remove

        Args:
            guild (discord.Guild): The guild that got removed
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild.name)
        await self.bot.logger.send_log(
            message=f"Left guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_join(self: Self, guild: discord.Guild) -> None:
        """Configures a new guild upon joining.

        Args:
            guild (discord.Guild): the guild that was joined
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild.name)

        log_channel = configuration.get_config_entry(
            guild.id, "core_guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"Joined guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )
