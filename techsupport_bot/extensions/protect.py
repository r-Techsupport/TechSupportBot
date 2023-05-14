"""Module for the protect extension of the discord bot."""
import datetime
import io
import re

import base
import discord
import expiringdict
import munch
import util
from discord.ext import commands


async def setup(bot):
    """Class to set up the protect options in the config file."""

    class Warning(bot.db.Model):
        """Class to set up warnings for the config file."""

        __tablename__ = "warnings"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        reason = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    config = bot.ExtensionConfig()
    config.add(
        key="channels",
        datatype="list",
        title="Protected channels",
        description="The list of channel ID's associated with the channels to auto-protect",
        default=[],
    )
    config.add(
        key="bypass_roles",
        datatype="list",
        title="Bypassed role names",
        description="The list of role names associated with bypassed roles by the auto-protect",
        default=[],
    )
    config.add(
        key="bypass_roles",
        datatype="list",
        title="Bypassed role names",
        description="The list of role names associated with bypassed roles by the auto-protect",
        default=[],
    )
    config.add(
        key="bypass_ids",
        datatype="list",
        title="Bypassed member ID's",
        description="The list of member ID's associated with bypassed members by the auto-protect",
        default=[],
    )
    config.add(
        key="length_limit",
        datatype="int",
        title="Max length limit",
        description="The max char limit on messages before they trigger an action by auto-protect",
        default=500,
    )
    config.add(
        key="string_map",
        datatype="dict",
        title="Keyword string map",
        description="Mapping of keyword strings to data defining the action taken by auto-protect",
        default={},
    )
    config.add(
        key="alert_channel",
        datatype="int",
        title="Alert channel ID",
        description="The ID of the channel to send auto-protect alerts to",
        default=None,
    )
    config.add(
        key="max_mentions",
        datatype="int",
        title="Max message mentions",
        description="Max number of mentions allowed in a message before triggering auto-protect",
        default=3,
    )
    config.add(
        key="linx_url",
        datatype="str",
        title="Linx API URL",
        description="The URL to an optional Linx (github.com/andreimarcu/linx-server)API for pastebinning factoid-all responses",
        default=None,
    )
    config.add(
        key="max_warnings",
        datatype="int",
        title="Max Warnings",
        description="The amount of warnings a user should be banned on",
        default=3,
    )
    config.add(
        key="ban_delete_duration",
        datatype="int",
        title="Ban delete duration (days)",
        description="The amount of days to delete messages for a user after they are banned",
        default=7,
    )
    config.add(
        key="max_purge_amount",
        datatype="int",
        title="Max Purge Amount",
        description="The max amount of messages allowed to be purged in one command",
        default=50,
    )

    await bot.add_cog(Protector(bot=bot, models=[Warning], extension_name="protect"))
    bot.add_extension_config("protect", config)


class ProtectEmbed(discord.Embed):
    """Class to make the embed for the protect command."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "Chat Protection"
        self.color = discord.Color.gold()


class Protector(base.MatchCog):
    """Class for the protector command."""

    ALERT_ICON_URL = "https://cdn.icon-icons.com/icons2/2063/PNG/512/alert_danger_warning_notification_icon_124692.png"
    CLIPBOARD_ICON_URL = (
        "https://icon-icons.com/icons2/203/PNG/128/diagram-30_24487.png"
    )
    CHARS_PER_NEWLINE = 80

    async def preconfig(self):
        """Method to preconfig the protect."""
        self.string_alert_cache = expiringdict.ExpiringDict(
            max_len=100, max_age_seconds=3600
        )

    async def match(self, config, ctx, content):
        """Method to match roles for the protect command."""
        # exit the match based on exclusion parameters
        if not str(ctx.channel.id) in config.extensions.protect.channels.value:
            await self.bot.logger.info(
                "Channel not in protected channels - ignoring protect check"
            )
            return False

        role_names = [role.name.lower() for role in getattr(ctx.author, "roles", [])]

        if any(
            role_name.lower() in role_names
            for role_name in config.extensions.protect.bypass_roles.value
        ):
            return False

        if ctx.author.id in config.extensions.protect.bypass_ids.value:
            return False

        return True

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        """Method to edit the raw message."""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        config = await self.bot.get_context_config(guild=guild)
        if not self.extension_enabled(config):
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message:
            return

        ctx = await self.bot.get_context(message)
        matched = await self.match(config, ctx, message.content)
        if not matched:
            return

        await self.response(config, ctx, message.content, None)

    async def response(self, config, ctx, content, _):
        """Method to define the response for the protect extension."""
        # check mass mentions first - return after handling
        if len(ctx.message.mentions) > config.extensions.protect.max_mentions.value:
            await self.handle_mass_mention_alert(config, ctx, content)
            return

        # search the message against keyword strings
        triggered_config = None
        for (
            keyword,
            filter_config,
        ) in config.extensions.protect.string_map.value.items():
            filter_config = munch.munchify(filter_config)
            search_keyword = keyword
            search_content = content

            regex = filter_config.get("regex")
            if regex:
                try:
                    match = re.search(regex, search_content)
                except re.error:
                    match = None
                if match:
                    filter_config["trigger"] = keyword
                    triggered_config = filter_config
                    if triggered_config.get("delete"):
                        break
            else:
                if filter_config.get("sensitive"):
                    search_keyword = search_keyword.lower()
                    search_content = search_content.lower()
                if search_keyword in search_content:
                    filter_config["trigger"] = keyword
                    triggered_config = filter_config
                    if triggered_config.get("delete"):
                        break

        if triggered_config:
            await self.handle_string_alert(config, ctx, content, triggered_config)
            if triggered_config.get("delete"):
                # the message is deleted, no need to pastebin it
                return

        # check length of content
        if len(content) > config.extensions.protect.length_limit.value or content.count(
            "\n"
        ) > self.max_newlines(config.extensions.protect.length_limit.value):
            await self.handle_length_alert(config, ctx, content)

    def max_newlines(self, max_length):
        """Method to set up the number of max lines."""
        return int(max_length / self.CHARS_PER_NEWLINE) + 1

    async def handle_length_alert(self, config, ctx, content):
        """Method to handle alert for the protect extension."""
        await ctx.message.delete()

        reason = "message too long (too many newlines or characters)"

        if not config.extensions.protect.linx_url.value:
            await self.send_default_delete_response(config, ctx, content, reason)
            return

        linx_embed = await self.create_linx_embed(config, ctx, content)
        if not linx_embed:
            await self.send_default_delete_response(config, ctx, content, reason)
            await self.send_alert(config, ctx, "Could not convert text to Linx paste")
            return

        await ctx.send(embed=linx_embed)

    async def handle_mass_mention_alert(self, config, ctx, content):
        """Method for handling mass mentions in an alert."""
        await ctx.message.delete()
        await self.handle_warn(ctx, ctx.author, "mass mention", bypass=True)
        await self.send_alert(config, ctx, f"Mass mentions from {ctx.author}")

    async def handle_string_alert(self, config, ctx, content, filter_config):
        """Method to handle a string alert for the protect extension."""
        if filter_config.warn:
            await self.handle_warn(ctx, ctx.author, filter_config.message, bypass=True)

        if filter_config.delete:
            await ctx.message.delete()

        await self.send_alert(
            config,
            ctx,
            f"Message contained trigger: {filter_config.trigger}",
        )

        cache_key = self.get_cache_key(ctx.guild, ctx.author, filter_config.trigger)
        if self.string_alert_cache.get(cache_key):
            return

        if filter_config.delete:
            await self.send_default_delete_response(
                config, ctx, content, filter_config.message
            )
        else:
            embed = ProtectEmbed(description=filter_config.message)
            await ctx.send(embed=embed)

        self.string_alert_cache[cache_key] = True

    async def handle_warn(self, ctx, user, reason, bypass=False):
        """Method to handle the warn of a user."""
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        warnings = await self.get_warnings(user, ctx.guild)

        new_count = len(warnings) + 1

        config = await self.bot.get_context_config(ctx)

        if new_count >= config.extensions.protect.max_warnings.value:
            if not bypass:
                should_ban = await ctx.confirm(
                    f"This user has exceeded the max warnings \
                        {config.extensions.protect.max_warnings.value}. \
                        Would you like to ban them instead?",
                    delete_after=True,
                )
                if not should_ban:
                    await ctx.send_deny_embed("No warnings have been set")
                    return

            await self.handle_ban(
                ctx,
                user,
                f"Over max warning count {new_count}/\
                    {config.extensions.protect.max_warnings.value} (final warning: {reason})",
                bypass=True,
            )
            await self.clear_warnings(user, ctx.guild)
            return

        await self.models.Warning(
            user_id=str(user.id), guild_id=str(ctx.guild.id), reason=reason
        ).create()
        embed = await self.generate_user_modified_embed(
            user, "warn", f"{reason} ({new_count} total warnings)"
        )
        await ctx.send(embed=embed)

    async def handle_unwarn(self, ctx, user, reason, bypass=False):
        """Method to handle an unwarn of a user."""
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        warnings = await self.get_warnings(user, ctx.guild)
        if not warnings:
            await ctx.send_deny_embed("There are no warnings for that user")
            return

        await self.clear_warnings(user, ctx.guild)

        embed = await self.generate_user_modified_embed(user, "unwarn", reason)
        await ctx.send(embed=embed)

    async def handle_ban(self, ctx, user, reason, bypass=False):
        """Method to handle the ban of a user."""
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        bans = await ctx.guild.bans()
        for ban in bans:
            if user == ban.user:
                await ctx.send_deny_embed("User is already banned.")
                return

        config = await self.bot.get_context_config(ctx)
        await ctx.guild.ban(
            user,
            reason=reason,
            delete_message_days=config.extensions.protect.ban_delete_duration.value,
        )

        embed = await self.generate_user_modified_embed(user, "ban", reason)

        await ctx.send(embed=embed)

    async def handle_unban(self, ctx, user, reason, bypass=False):
        """Method to handle an unban of a user."""
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        try:
            await ctx.guild.unban(user, reason=reason)
        except discord.NotFound:
            await ctx.send_deny_embed("This user is not banned, or does not exist")
            return

        embed = await self.generate_user_modified_embed(user, "unban", reason)

        await ctx.send(embed=embed)

    async def handle_kick(self, ctx, user, reason, bypass=False):
        """Method to handle the kicking from the discord of a user."""
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        await ctx.guild.kick(user, reason=reason)

        embed = await self.generate_user_modified_embed(user, "kick", reason)

        await ctx.send(embed=embed)

    async def clear_warnings(self, user, guild):
        """Method to clear warnings of a user in discord."""
        await self.models.Warning.delete.where(
            self.models.Warning.user_id == str(user.id)
        ).where(self.models.Warning.guild_id == str(guild.id)).gino.status()

    async def generate_user_modified_embed(self, user, action, reason):
        """Method to generate the user embed with the reason."""
        embed = discord.Embed(
            title="Chat Protection", description=f"{action.upper()} `{user}`"
        )
        embed.set_footer(text=f"Reason: {reason}")
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.color = discord.Color.gold()

        return embed

    def get_cache_key(self, guild, user, trigger):
        """Method to get the cache key of the user."""
        return f"{guild.id}_{user.id}_{trigger}"

    async def can_execute(self, ctx, target):
        """Method to not execute on admin users."""
        if target.id == ctx.author.id:
            await ctx.send_deny_embed("You cannot do that to yourself")
            return False
        if target.id == self.bot.user.id:
            await ctx.send_deny_embed("It would be silly to do that to myself")
            return False
        try:
            if target.top_role >= ctx.author.top_role:
                await ctx.send_deny_embed(
                    f"Your top role is not high enough to do that to `{target}`"
                )
                return False
        except AttributeError:
            return True
        return True

    async def send_alert(self, config, ctx, message):
        """Method to send an alert to the channel about a protect command."""
        try:
            alert_channel = ctx.guild.get_channel(
                int(config.extensions.protect.alert_channel.value)
            )
        except TypeError:
            alert_channel = None

        if not alert_channel:
            return

        embed = discord.Embed(title="Protect Alert", description=message)

        if len(ctx.message.content) >= 256:
            message_content = ctx.message.content[0:256]
        else:
            message_content = ctx.message.content

        embed.add_field(name="Channel", value=f"#{ctx.channel.name}")
        embed.add_field(name="User", value=ctx.author.mention)
        embed.add_field(name="Message", value=message_content, inline=False)
        embed.add_field(name="URL", value=ctx.message.jump_url, inline=False)

        embed.set_thumbnail(url=self.ALERT_ICON_URL)
        embed.color = discord.Color.red()

        await alert_channel.send(embed=embed)

    async def send_default_delete_response(self, config, ctx, content, reason):
        """Method for the default delete of a message."""
        embed = ProtectEmbed(description=f"Message deleted. Reason: *{reason}*")
        await ctx.send(embed=embed)
        await ctx.author.send(f"Deleted message: ```{content[:1994]}```")

    async def get_warnings(self, user, guild):
        """Method to get the warnings of a user."""
        warnings = (
            await self.models.Warning.query.where(
                self.models.Warning.user_id == str(user.id)
            )
            .where(self.models.Warning.guild_id == str(guild.id))
            .gino.all()
        )
        return warnings

    async def create_linx_embed(self, config, ctx, content):
        """Method to create a link for long messages."""
        if not content:
            return None

        headers = {
            "Linx-Expiry": "1800",
            "Linx-Randomize": "yes",
            "Accept": "application/json",
        }
        file = {"file": io.StringIO(content)}
        response = await self.bot.http_call(
            "post", config.extensions.protect.linx_url.value, headers=headers, data=file
        )

        url = response.get("url")
        if not url:
            return None

        embed = discord.Embed(description=url)

        embed.add_field(name="Paste Link", value=url)
        embed.description = content[0:100].replace("\n", " ")
        embed.set_author(
            name=f"Paste by {ctx.author}", icon_url=ctx.author.display_avatar.url
        )
        embed.set_footer(text="Note: long messages are automatically pasted")
        embed.color = discord.Color.blue()

        return embed

    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.command(
        name="ban",
        brief="Bans a user",
        description="Bans a user with a given reason",
        usage="@user [reason]",
    )
    async def ban_user(self, ctx, user: discord.User, *, reason: str = None):
        """Method to ban a user from discord."""

        # Uses the discord.Member class to get the top role attribute if the
        # user is a part of the target guild
        if ctx.guild.get_member(user.id) is not None:
            await self.handle_ban(ctx, ctx.guild.get_member(user.id), reason)
        else:
            await self.handle_ban(ctx, user, reason)

        config = await self.bot.get_context_config(ctx)
        await self.send_alert(config, ctx, "Ban command")

    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.command(
        name="unban",
        brief="Unbans a user",
        description="Unbans a user with a given reason",
        usage="@user [reason]",
    )
    async def unban_user(self, ctx, user: discord.User, *, reason: str = None):
        """Method to unban a user from discord."""

        # Uses the discord.Member class to get the top role attribute if the
        # user is a part of the target guild
        if ctx.guild.get_member(user.id) is not None:
            await self.handle_unban(ctx, ctx.guild.get_member(user.id), reason)
        else:
            await self.handle_unban(ctx, user, reason)

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="kick",
        brief="Kicks a user",
        description="Kicks a user with a given reason",
        usage="@user [reason]",
    )
    async def kick_user(self, ctx, user: discord.Member, *, reason: str = None):
        """Method to kick a user from discord."""
        await self.handle_kick(ctx, user, reason)

        config = await self.bot.get_context_config(ctx)
        await self.send_alert(config, ctx, "Kick command")

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="warn",
        brief="Warns a user",
        description="Warn a user with a given reason",
        usage="@user [reason]",
    )
    async def warn_user(self, ctx, user: discord.Member, *, reason: str = None):
        """Method to warn a user of wrongdoing in discord."""
        await self.handle_warn(ctx, user, reason)

        config = await self.bot.get_context_config(ctx)
        await self.send_alert(config, ctx, "Warn command")

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="unwarn",
        brief="Unwarns a user",
        description="Unwarns a user with a given reason",
        usage="@user [reason]",
    )
    async def unwarn_user(self, ctx, user: discord.Member, *, reason: str = None):
        """Method to unwarn a user on discord."""
        await self.handle_unwarn(ctx, user, reason)

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="warnings",
        brief="Gets warnings",
        description="Gets warnings for a user",
        usage="@user",
    )
    async def get_warnings_command(self, ctx, user: discord.User):
        """Method to get the warnings of a user in discord."""
        warnings = await self.get_warnings(user, ctx.guild)
        if not warnings:
            await ctx.send_deny_embed("There are no warnings for that user")
            return

        embed = discord.Embed(title=f"Warnings for {user}")
        for warning in warnings:
            embed.add_field(name=warning.time, value=warning.reason, inline=False)

        embed.set_thumbnail(url=user.display_avatar.url)

        embed.color = discord.Color.red()

        await ctx.send(embed=embed)

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="mute",
        brief="Mutes a user",
        description="Assigns the Muted role to a user (you need to create/configure this role)",
        usage="@user",
    )
    async def mute(self, ctx, user: discord.Member, *, reason: str = None):
        """Method to mute a user in discord."""
        can_execute = await self.can_execute(ctx, user)
        if not can_execute:
            return

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            await ctx.send_deny_embed("The `Muted` role does not exist")
            return

        await user.add_roles(role)

        embed = await self.generate_user_modified_embed(user, "muted", reason)

        await ctx.send(embed=embed)

        config = await self.bot.get_context_config(ctx)
        await self.send_alert(config, ctx, "Mute command")

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="unmute",
        brief="Unutes a user",
        description="Removes the Muted role from a user (you need to create/configure this role)",
        usage="@user",
    )
    async def unmute(self, ctx, user: discord.Member, reason: str = None):
        """Method to unmute a user in discord."""
        can_execute = await self.can_execute(ctx, user)
        if not can_execute:
            return

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            await ctx.send_deny_embed("The `Muted` role does not exist")
            return

        await user.remove_roles(role)

        embed = await self.generate_user_modified_embed(user, "unmuted", reason)

        await ctx.send(embed=embed)

    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.group(
        brief="Executes a purge command",
        description="Executes a purge command",
    )
    async def purge(self, ctx):
        """Method to purge messages in discord."""
        pass

    @purge.command(
        name="amount",
        aliases=["x"],
        brief="Purges messages by amount",
        description="Purges the current channel's messages based on amoun",
        usage="[amount]",
    )
    async def purge_amount(self, ctx, amount: int = 1):
        """Method to get the amount to purge messages in discord."""
        config = await self.bot.get_context_config(ctx)

        if amount <= 0 or amount > config.extensions.protect.max_purge_amount.value:
            amount = config.extensions.protect.max_purge_amount.value

        await ctx.channel.purge(limit=amount)

        await self.send_alert(config, ctx, "Purge command")

    @purge.command(
        name="duration",
        aliases=["d"],
        brief="Purges messages by duration",
        description="Purges the current channel's messages up to a time",
        usage="[duration (minutes)]",
    )
    async def purge_duration(self, ctx, duration_minutes: int):
        """Method to purge a channel's message up to a time."""
        if duration_minutes < 0:
            await ctx.send_deny_embed("I can't use that input")
            return

        timestamp = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=duration_minutes
        )

        config = await self.bot.get_context_config(ctx)

        await ctx.channel.purge(
            after=timestamp, limit=config.extensions.protect.max_purge_amount.value
        )

        await self.send_alert(config, ctx, "Purge command")
