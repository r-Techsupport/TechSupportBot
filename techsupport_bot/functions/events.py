"""All of the discord event listeners where they used for logging"""

import datetime
import sys
from typing import Optional, Sequence, Union

import discord
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Registers the EventLogger Cog"""
    await bot.add_cog(EventLogger(bot=bot))


class EventLogger(cogs.BaseCog):
    """This is the cog that holds all of the discord event listeners
    For the explicit purpose of logging, not taking further action
    """

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_edit"""
        # this seems to spam, not sure why
        if before.content == after.content:
            return

        guild = getattr(before.channel, "guild", None)

        # Ignore ephemeral slash command messages
        if not guild and before.type == discord.MessageType.chat_input_command:
            return

        attrs = ["content", "embeds"]
        diff = auxiliary.get_object_diff(before, after, attrs)
        embed = discord.Embed()
        embed = auxiliary.add_diff_fields(embed, diff)
        embed.add_field(name="Author", value=before.author)
        embed.add_field(name="Channel", value=getattr(before.channel, "name", "DM"))
        embed.add_field(
            name="Server",
            value=guild,
        )
        embed.set_footer(text=f"Author ID: {before.author.id}")

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"Message edit detected on message with ID {before.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=before.channel.guild, channel=before.channel),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_delete"""
        guild = getattr(message.channel, "guild", None)

        # Ignore ephemeral slash command messages
        if not guild and message.type == discord.MessageType.chat_input_command:
            return

        embed = discord.Embed()
        embed.add_field(name="Content", value=message.content[:1024] or "None")
        if len(message.content) > 1024:
            embed.add_field(name="\a", value=message.content[1025:2048])
        if len(message.content) > 2048:
            embed.add_field(name="\a", value=message.content[2049:3072])
        if len(message.content) > 3072:
            embed.add_field(name="\a", value=message.content[3073:4096])
        embed.add_field(name="Author", value=message.author)
        embed.add_field(
            name="Channel",
            value=getattr(message.channel, "name", "DM"),
        )
        embed.add_field(name="Server", value=getattr(guild, "name", "None"))
        embed.set_footer(text=f"Author ID: {message.author.id}")

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=f"Message with ID {message.id} deleted",
            level=LogLevel.INFO,
            context=LogContext(guild=message.channel.guild, channel=message.channel),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_bulk_message_delete
        """
        guild = getattr(messages[0].channel, "guild", None)

        unique_channels = set()
        unique_servers = set()
        for message in messages:
            unique_channels.add(message.channel.name)
            unique_servers.add(
                f"{message.channel.guild.name} ({message.channel.guild.id})"
            )

        embed = discord.Embed()
        embed.add_field(name="Channels", value=",".join(unique_channels))
        embed.add_field(name="Servers", value=",".join(unique_servers))

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=f"{len(messages)} messages bulk deleted!",
            level=LogLevel.INFO,
            context=LogContext(
                guild=messages[0].channel.guild, channel=messages[0].channel
            ),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]
    ):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_add"""
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

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
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
        self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]
    ):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_remove"""
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

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
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
        self, message: discord.Message, reactions: list[discord.Reaction]
    ):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_clear
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

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"{len(reactions)} cleared from message with ID {message.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=message.channel.guild, channel=message.channel),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_delete
        """
        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild.name)

        log_channel = await self.bot.get_log_channel_from_guild(
            channel.guild, key="guild_events_channel"
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
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_create
        """
        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild.name)
        log_channel = await self.bot.get_log_channel_from_guild(
            getattr(channel, "guild", None), key="guild_events_channel"
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
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_update
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

        log_channel = await self.bot.get_log_channel_from_guild(
            before.guild, key="guild_events_channel"
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
        self,
        channel: Union[discord.abc.GuildChannel, discord.Thread],
        _last_pin: Optional[datetime.datetime],
    ):
        """
        See:
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_pins_update
        """
        embed = discord.Embed()
        embed.add_field(name="Channel Name", value=channel.name)
        embed.add_field(name="Server", value=channel.guild)

        log_channel = await self.bot.get_log_channel_from_guild(
            channel.guild, key="guild_events_channel"
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
    async def on_guild_integrations_update(self, guild: discord.Guild):
        """
        See:
        https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_integrations_update
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild)
        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=f"Integrations updated in guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel: discord.abc.GuildChannel):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_webhooks_update"""
        embed = discord.Embed()
        embed.add_field(name="Channel", value=channel.name)
        embed.add_field(name="Server", value=channel.guild)

        log_channel = await self.bot.get_log_channel_from_guild(
            channel.guild, key="guild_events_channel"
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
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_update"""
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

            log_channel = await self.bot.get_log_channel_from_guild(
                getattr(before, "guild", None), key="member_events_channel"
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
    async def on_member_remove(self, member: discord.Member):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_remove"""
        embed = discord.Embed()
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Server", value=member.guild.name)
        log_channel = await self.bot.get_log_channel_from_guild(
            getattr(member, "guild", None), key="member_events_channel"
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
    async def on_guild_remove(self, guild: discord.Guild):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_remove"""
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild.name)
        await self.bot.logger.send_log(
            message=f"Left guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Configures a new guild upon joining.

        parameters:
            guild (discord.Guild): the guild that was joined
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"Joined guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_update
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

        log_channel = await self.bot.get_log_channel_from_guild(
            before, key="guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=f"Guild with ID {before.id} updated",
            level=LogLevel.INFO,
            context=LogContext(guild=before),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_create"""
        embed = discord.Embed()
        embed.add_field(name="Server", value=role.guild.name)
        log_channel = await self.bot.get_log_channel_from_guild(
            role.guild, key="guild_events_channel"
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
    async def on_guild_role_delete(self, role: discord.Role):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_delete"""
        embed = discord.Embed()
        embed.add_field(name="Server", value=role.guild.name)
        log_channel = await self.bot.get_log_channel_from_guild(
            role.guild, key="guild_events_channel"
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
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_update"""
        attrs = ["color", "mentionable", "name", "permissions", "position", "tags"]
        diff = auxiliary.get_object_diff(before, after, attrs)

        embed = discord.Embed()
        embed = auxiliary.add_diff_fields(embed, diff)
        embed.add_field(name="Server", value=before.name)

        log_channel = await self.bot.get_log_channel_from_guild(
            before.guild, key="guild_events_channel"
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
        self,
        guild: discord.Guild,
        before: Sequence[discord.Emoji],
        _: Sequence[discord.Emoji],
    ):
        """
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_emojis_update
        """
        embed = discord.Embed()
        embed.add_field(name="Server", value=before.name)

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="guild_events_channel"
        )
        await self.bot.logger.send_log(
            message=f"Emojis updated in guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=before),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_member_ban(
        self, guild: discord.Guild, user: Union[discord.User, discord.Member]
    ):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_ban"""
        embed = discord.Embed()
        embed.add_field(name="User", value=user)
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="member_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"User with ID {user.id} banned from guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_unban"""
        embed = discord.Embed()
        embed.add_field(name="User", value=user)
        embed.add_field(name="Server", value=guild.name)

        log_channel = await self.bot.get_log_channel_from_guild(
            guild, key="member_events_channel"
        )

        await self.bot.logger.send_log(
            message=f"User with ID {user.id} unbanned from guild with ID {guild.id}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild),
            channel=log_channel,
            embed=embed,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join"""
        embed = discord.Embed()
        embed.add_field(name="Member", value=member)
        embed.add_field(name="Server", value=member.guild.name)
        log_channel = await self.bot.get_log_channel_from_guild(
            getattr(member, "guild", None), key="member_events_channel"
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

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        """
        See: https://discordpy.readthedocs.io/en/latest/ext/commands/api.html#discord.on_command
        """
        embed = discord.Embed()
        embed.add_field(name="User", value=ctx.author)
        embed.add_field(name="Channel", value=getattr(ctx.channel, "name", "DM"))
        embed.add_field(name="Server", value=getattr(ctx.guild, "name", "None"))

        log_channel = await self.bot.get_log_channel_from_guild(
            ctx.guild, key="logging_channel"
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

    @commands.Cog.listener()
    async def on_error(self, event_method):
        """Catches non-command errors and sends them to the error logger for processing.

        parameters:
            event_method (str): the event method name associated with the error (eg. on_message)
        """
        _, exception, _ = sys.exc_info()
        await self.bot.logger.send_log(
            message=f"Bot error in {event_method}: {exception}",
            level=LogLevel.ERROR,
            exception=exception,
        )

    @commands.Cog.listener()
    async def on_connect(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_connect"""
        await self.bot.logger.send_log(
            message="Connected to Discord",
            level=LogLevel.INFO,
            console_only=True,
        )

    @commands.Cog.listener()
    async def on_resumed(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_resumed"""
        await self.bot.logger.send_log(
            message="Resume event",
            level=LogLevel.INFO,
            console_only=True,
        )

    @commands.Cog.listener()
    async def on_disconnect(self):
        """See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_disconnect"""
        await self.bot.logger.send_log(
            message="Disconnected from Discord",
            level=LogLevel.INFO,
            console_only=True,
        )
