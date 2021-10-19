import asyncio
import collections
import datetime
import io

import base
import discord
import munch
from discord.ext import commands


def setup(bot):
    class Warning(bot.db.Model):
        __tablename__ = "warnings"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        reason = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    config = bot.PluginConfig()
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
        description="The max char limit on messages before they trigger an action by the auto-protect",
        default=500,
    )
    config.add(
        key="string_map",
        datatype="dict",
        title="Keyword string map",
        description="The mapping of keyword strings to data defining the action to take by the auto-protect",
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
        description="The max number of mentions allowed in a message before triggering the auto-protect",
        default=3,
    )
    config.add(
        key="linx_url",
        datatype="str",
        title="Linx API URL",
        description="The URL to an optional Linx API for pastebinning long messages by the auto-protect",
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
    config.add(
        key="string_alert_cache_time",
        datatype="int",
        title="String alert caching time",
        description="The number of seconds that must pass before the same trigger response is sent to a user",
        default=600,
    )

    bot.process_plugin_setup(cogs=[Protector], config=config, models=[Warning])


class Protector(base.MatchCog):

    ALERT_ICON_URL = "https://cdn.icon-icons.com/icons2/2063/PNG/512/alert_danger_warning_notification_icon_124692.png"
    CLIPBOARD_ICON_URL = (
        "https://icon-icons.com/icons2/203/PNG/128/diagram-30_24487.png"
    )
    CACHE_CLEAN_MINUTES = 0.0833333

    async def preconfig(self):
        self.string_alert_cache = collections.defaultdict(
            lambda: collections.defaultdict(dict)
        )
        self.cache_lock = asyncio.Lock()
        await self.bot.loop.create_task(self.cache_clean_loop())

    async def clean_string_alert_cache(self):
        for guild_cache in self.string_alert_cache.values():
            for user_cache in guild_cache.values():
                for expire_time in user_cache.values():
                    if datetime.datetime.utcnow() > expire_time:
                        await self.bot.logger.debug(
                            "Clearing protect plugin trigger cache since time expired"
                        )
                        del expire_time
                # if we've deleted everything in the user cache, delete the user key too
                if len(user_cache) == 0:
                    await self.bot.logger.debug(
                        "Clearing protect plugin user cache since no triggers found"
                    )
                    del user_cache

    async def cache_clean_loop(self):
        while True:
            async with self.cache_lock:
                await self.clean_string_alert_cache()
            await self.bot.logger.debug(
                "Sleeping until next protect plugin cache clean cycle"
            )
            await asyncio.sleep(int(self.CACHE_CLEAN_MINUTES * 60))

    async def match(self, config, ctx, content):
        # exit the match based on exclusion parameters
        if not str(ctx.channel.id) in config.plugins.protect.channels.value:
            await self.bot.logger.info(
                "Channel not in protected channels - ignoring protect check"
            )
            return False

        role_names = [role.name.lower() for role in getattr(ctx.author, "roles", [])]

        if any(
            role_name.lower() in role_names
            for role_name in config.plugins.protect.bypass_roles.value
        ):
            return False

        if ctx.author.id in config.plugins.protect.bypass_ids.value:
            return False

        return True

    async def response(self, config, ctx, content, _):
        # check mass mentions first - return after handling
        if len(ctx.message.mentions) > config.plugins.protect.max_mentions.value:
            await self.handle_mass_mention_alert(config, ctx, content)
            return

        # search the message against keyword strings
        triggered_config = None
        for keyword, filter_config in config.plugins.protect.string_map.value.items():
            filter_config = munch.munchify(filter_config)
            search_keyword = keyword
            search_content = content

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
        if len(content) > config.plugins.protect.length_limit.value:
            await self.handle_length_alert(config, ctx, content)

    async def get_warnings(self, user, guild):
        warnings = (
            await self.models.Warning.query.where(
                self.models.Warning.user_id == str(user.id)
            )
            .where(self.models.Warning.guild_id == str(guild.id))
            .gino.all()
        )
        return warnings

    async def handle_warn(self, ctx, user, reason, bypass=False, alert=True):
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        warnings = await self.get_warnings(user, ctx.guild)

        new_count = len(warnings) + 1

        config = await self.bot.get_context_config(ctx)

        if new_count >= config.plugins.protect.max_warnings.value:
            # ban the user instead of saving new warning count
            ban_reason = f"Over max warning count {new_count}/{config.plugins.protect.max_warnings.value} (final warning: {reason})"
            await self.handle_ban(ctx, user, ban_reason, bypass=True)
        else:
            await self.models.Warning(
                user_id=str(user.id), guild_id=str(ctx.guild.id), reason=reason
            ).create()

            embed = await self.generate_user_modified_embed(
                user, "warn", f"{reason} ({new_count} total warnings)"
            )
            await self.bot.send_with_mention(ctx, embed=embed)

    async def handle_unwarn(self, ctx, user, reason, bypass=False):
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        warnings = await self.get_warnings(user, ctx.guild)
        if not warnings:
            await self.bot.send_with_mention(ctx, "There are no warnings for that user")
            return

        await self.models.Warning.delete.where(
            self.models.Warning.user_id == str(user.id)
        ).where(self.models.Warning.guild_id == str(ctx.guild.id)).gino.status()

        embed = await self.generate_user_modified_embed(user, "UNWARNED", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    async def handle_ban(self, ctx, user, reason, bypass=False):
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        config = await self.bot.get_context_config(ctx)
        await ctx.guild.ban(
            user,
            reason=reason,
            delete_message_days=config.plugins.protect.ban_delete_duration.value,
        )

        embed = await self.generate_user_modified_embed(user, "ban", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    async def handle_unban(self, ctx, user, reason, bypass=False):
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        await user.unban(reason=reason)

        embed = await self.generate_user_modified_embed(user, "unban", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    async def handle_kick(self, ctx, user, reason, bypass=False):
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        await ctx.guild.kick(user, reason=reason)

        embed = await self.generate_user_modified_embed(user, "kick", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    async def generate_user_modified_embed(self, user, action, reason):
        embed = discord.Embed(
            title=f"{action.upper()}: {user}", description=f"Reason: {reason}"
        )
        embed.set_thumbnail(url=user.avatar_url)

        return embed

    async def handle_length_alert(self, config, ctx, content):
        await ctx.message.delete()

        reason = (
            f"message longer than {config.plugins.protect.length_limit.value} chars"
        )

        if not config.plugins.protect.linx_url.value:
            await self.send_default_delete_response(config, ctx, content, reason)
            return

        linx_embed = await self.create_linx_embed(config, ctx, content)
        if not linx_embed:
            await self.send_default_delete_response(config, ctx, content, reason)
            await self.send_alert(config, ctx, "Could not convert text to Linx paste")
            return

        await self.bot.send_with_mention(ctx, embed=linx_embed)

    async def handle_mass_mention_alert(self, config, ctx, content):
        await ctx.message.delete()
        await self.handle_warn(ctx, ctx.author, "mass mention", bypass=True)
        await self.send_alert(config, ctx, f"Mass mentions from {ctx.author}")

    async def send_default_delete_response(self, config, ctx, content, reason):
        await self.bot.send_with_mention(
            ctx,
            f"I deleted your message because: `{reason}`",
        )
        await ctx.author.send(f"Deleted message: ```{content[:1994]}```")

    async def send_alert(self, config, ctx, message):
        try:
            alert_channel = ctx.guild.get_channel(
                int(config.plugins.protect.alert_channel.value)
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

        await alert_channel.send(embed=embed)

    async def create_linx_embed(self, config, ctx, content):
        if not content:
            return None

        headers = {
            "Linx-Expiry": "1800",
            "Linx-Randomize": "yes",
            "Accept": "application/json",
        }
        file = {"file": io.StringIO(content)}
        response = await self.bot.http_call(
            "post", config.plugins.protect.linx_url.value, headers=headers, data=file
        )

        url = response.get("url")
        if not url:
            return None

        embed = discord.Embed(title=f"Paste by {ctx.author}", description=url)

        if len(content) > 256:
            content = content[:256]

        embed.add_field(name="Preview", value=content.replace("\n", " "))

        embed.set_thumbnail(url=self.CLIPBOARD_ICON_URL)

        return embed

    async def handle_string_alert(self, config, ctx, content, filter_config):
        if filter_config.warn:
            await self.handle_warn(ctx, ctx.author, filter_config.message, bypass=True)

        if filter_config.delete:
            await ctx.message.delete()

        await self.send_alert(
            config,
            ctx,
            f"Message contained trigger: {filter_config.trigger}",
        )

        # check if this response data has triggered a response recently
        if self.user_cached(ctx, filter_config.trigger):
            return

        if filter_config.delete:
            await self.send_default_delete_response(
                config, ctx, content, filter_config.message
            )
        else:
            await self.bot.send_with_mention(ctx, filter_config.message)

        async with self.cache_lock:
            await self.cache_user(config, ctx, filter_config.trigger)

    async def cache_user(self, config, ctx, trigger):
        try:
            user_cache = self.string_alert_cache[ctx.guild.id][ctx.author.id]
            user_cache[trigger] = datetime.datetime.utcnow() + datetime.timedelta(
                seconds=config.plugins.protect.string_alert_cache_time.value
            )

        except Exception as e:
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not cache trigger response user: {e}",
                send=True,
            )

    def user_cached(self, ctx, trigger):
        user_cache = self.string_alert_cache[ctx.guild.id][ctx.author.id]
        expire_time = user_cache.get(trigger)

        if not expire_time:
            return False

        if datetime.datetime.utcnow() > expire_time:
            return False

        return True

    async def can_execute(self, ctx, target):
        if target.id == self.bot.user.id:
            await self.bot.send_with_mention(ctx, f"It would be silly to warn myself")
            return False

        if target.top_role >= ctx.author.top_role:
            await self.bot.send_with_mention(
                ctx, f"Your role is too low to do that to {target}"
            )
            return False

        return True

    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.command(
        name="ban",
        brief="Bans a user",
        description="Bans a user with a given reason",
        usage="@user [reason]",
    )
    async def ban_user(self, ctx, user: discord.Member, *, reason: str = None):
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
    async def unban_user(self, ctx, user: discord.Member, *, reason: str = None):
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
        warnings = await self.get_warnings(user, ctx.guild)
        if not warnings:
            await self.bot.send_with_mention(ctx, "There are no warnings for that user")
            return

        embed = discord.Embed(title=f"Warnings for {user}")
        for warning in warnings:
            embed.add_field(name="Reason", value=warning.reason, inline=False)

        embed.set_thumbnail(url=user.avatar_url)

        await self.bot.send_with_mention(ctx, embed=embed)

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="mute",
        brief="Mutes a user",
        description="Assigns the Muted role to a user (you need to create/configure this role)",
        usage="@user",
    )
    async def mute(self, ctx, user: discord.Member, *, reason: str = None):
        can_execute = await self.can_execute(ctx, user)
        if not can_execute:
            return

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            await self.bot.send_with_mention(ctx, "The `Muted` role does not exist")
            return

        await user.add_roles(role)

        embed = await self.generate_user_modified_embed(user, "muted", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

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
        can_execute = await self.can_execute(ctx, user)
        if not can_execute:
            return

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            await self.bot.send_with_mention(ctx, "The `Muted` role does not exist")
            return

        await user.remove_roles(role)

        embed = await self.generate_user_modified_embed(user, "umuted", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.group(
        brief="Executes a purge command",
        description="Executes a purge command",
    )
    async def purge(self, ctx):
        pass

    @purge.command(
        name="amount",
        aliases=["x"],
        brief="Purges messages by amount",
        description="Purges the current channel's messages based on amoun",
        usage="[amount]",
    )
    async def purge_amount(self, ctx, amount: int = 1):
        config = await self.bot.get_context_config(ctx)

        if amount <= 0 or amount > config.plugins.protect.max_purge_amount.value:
            amount = config.plugins.protect.max_purge_amount.value

        await ctx.channel.purge(limit=amount)

        await self.send_alert(config, ctx, f"Purge command")

    @purge.command(
        name="duration",
        aliases=["d"],
        brief="Purges messages by duration",
        description="Purges the current channel's messages up to a time",
        usage="[duration (minutes)]",
    )
    async def purge_duration(self, ctx, duration_minutes: int):
        if duration_minutes < 0:
            await self.bot.send_with_mention(ctx, "I can't use that input")
            return

        timestamp = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=duration_minutes
        )

        config = await self.bot.get_context_config(ctx)

        await ctx.channel.purge(
            after=timestamp, limit=config.plugins.protect.max_purge_amount.value
        )

        await self.send_alert(config, ctx, f"Purge command")
