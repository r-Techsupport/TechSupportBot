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
        description="The list of channel ID's associated with the channels to protect",
        default=[],
    )
    config.add(
        key="bypass_roles",
        datatype="list",
        title="Bypassed role names",
        description="The list of role names associated with bypassed roles",
        default=[],
    )
    config.add(
        key="bypass_ids",
        datatype="list",
        title="Bypassed member ID's",
        description="The list of member ID's associated with bypassed members",
        default=[],
    )
    config.add(
        key="length_limit",
        datatype="int",
        title="Max length limit",
        description="The max char limit on messages before they trigger an action",
        default=500,
    )
    config.add(
        key="string_map",
        datatype="dict",
        title="Keyword string map",
        description="The mapping of keyword strings to data defining the action to take",
        default={},
    )
    config.add(
        key="alert_channel",
        datatype="int",
        title="Alert channel ID",
        description="The ID of the channel to send protect alerts to",
        default=None,
    )
    config.add(
        key="max_mentions",
        datatype="int",
        title="Max message mentions",
        description="The max number of mentions allowed in a message",
        default=3,
    )
    config.add(
        key="linx_url",
        datatype="str",
        title="Linx API URL",
        description="The URL to an optional Linx API for pastebinning long messages",
        default=None,
    )

    bot.process_plugin_setup(cogs=[Protector], config=config, models=[Warning])


class Protector(base.MatchCog):

    ALERT_ICON_URL = "https://cdn.icon-icons.com/icons2/2063/PNG/512/alert_danger_warning_notification_icon_124692.png"
    CLIPBOARD_ICON_URL = (
        "https://icon-icons.com/icons2/203/PNG/128/diagram-30_24487.png"
    )
    MAX_WARNINGS = 3
    DELETE_MESSAGES_DAYS = 7

    async def match(self, config, ctx, content):
        # exit the match based on exclusion parameters
        if not ctx.channel.id in config.plugins.protect.channels.value:
            return False

        admin = await self.bot.is_bot_admin(ctx)
        if admin:
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

    async def response(self, config, ctx, content):
        # check length of content
        if len(content) > config.plugins.protect.length_limit.value:
            await self.handle_length_alert(config, ctx, content)
            return

        # check mass mentions
        if len(ctx.message.mentions) > config.plugins.protect.max_mentions.value:
            await self.handle_mass_mention_alert(config, ctx, content)
            return

        # finally search the message against keyword strings
        for keyword, filter_config in config.plugins.protect.string_map.value.items():
            filter_config = munch.munchify(filter_config)
            search_keyword = keyword
            search_content = content

            if filter_config.get("sensitive"):
                search_keyword = search_keyword.lower()
                search_content = search_content.lower()

            if search_keyword in search_content:
                filter_config["trigger"] = keyword
                await self.handle_string_alert(config, ctx, content, filter_config)
                return

    async def get_warnings(self, user, guild):
        warnings = (
            await self.models.Warning.query.where(
                self.models.Warning.user_id == str(user.id)
            )
            .where(self.models.Warning.guild_id == str(guild.id))
            .gino.all()
        )
        return warnings

    async def handle_warn(self, ctx, user, reason):
        warnings = await self.get_warnings(user, ctx.guild)

        new_count = len(warnings) + 1

        if new_count >= self.MAX_WARNINGS:
            # ban the user instead of saving new warning count
            await ctx.guild.ban(
                ctx.author, reason=reason, delete_message_days=self.DELETE_MESSAGES_DAYS
            )

            ban_reason = f"Over max warning count {new_count}/{self.MAX_WARNINGS} (final warning: {reason})"
    
            embed = await self.generate_user_modified_embed(
                ctx.author, "ban", ban_reason
            )
        else:
            await self.models.Warning(
                user_id=str(ctx.author.id), guild_id=str(ctx.guild.id), reason=reason
            ).create()

            embed = await self.generate_user_modified_embed(
                ctx.author, "warn", f"{reason} ({new_count} total warnings)"
            )

        await self.bot.send_with_mention(ctx, embed=embed)

    async def handle_unwarn(self, ctx, user, reason):
        warnings = await self.get_warnings(user, ctx.guild)
        if not warnings:
            await self.bot.send_with_mention(ctx, "There are no warnings for that user")
            return

        await self.models.Warning.delete.where(
            self.models.Warning.user_id == str(user.id)
        ).where(self.models.Warning.guild_id == str(ctx.guild.id)).gino.status()

        embed = await self.generate_user_modified_embed(ctx.author, "UNWARNED", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    async def handle_ban(self, ctx, user, reason):
        await ctx.guild.ban(
            user, reason=reason, delete_message_days=self.DELETE_MESSAGES_DAYS
        )

        embed = await self.generate_user_modified_embed(user, "ban", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    async def handle_unban(self, ctx, user, reason):
        await user.unban(reason=reason)

        embed = await self.generate_user_modified_embed(user, "unban", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    async def handle_kick(self, ctx, user, reason):
        await ctx.guild.kick(user, reason=reason)

        embed = await self.generate_user_modified_embed(user, "kick", reason)

        await self.bot.send_with_mention(ctx, embed=embed)

    async def generate_user_modified_embed(self, user, action, reason):
        embed = self.bot.embed_api.Embed(
            title=f"{action.upper()}: {user}", description=f"Reason: {reason}"
        )
        embed.set_thumbnail(url=user.avatar_url)

        embed.timestamp = datetime.datetime.utcnow()

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
            return

        await self.bot.send_with_mention(ctx, embed=linx_embed)

    async def handle_mass_mention_alert(self, config, ctx, content):
        await ctx.message.delete()
        await self.handle_warn(ctx, ctx.author, "mass mention")

    async def send_default_delete_response(self, config, ctx, content, reason):
        await self.bot.send_with_mention(
            ctx,
            f"I deleted your message because: {reason}. Check your DM's for the original message",
        )
        await ctx.author.send(f"Deleted message: ```{content[:1994]}```")

    async def send_admin_alert(self, config, ctx, message):
        alert_channel = ctx.guild.get_channel(
            int(config.plugins.protect.alert_channel.value)
        )
        if not alert_channel:
            return

        embed = self.bot.embed_api.Embed(
            title="Protect Plugin Alert", description=f"{message}"
        )

        embed.add_field(name="User", value=ctx.author.mention)
        embed.add_field(name="Channel", value=f"#{ctx.channel.name}")
        embed.add_field(name="Message", value=ctx.message.content, inline=False)

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

        embed = self.bot.embed_api.Embed(
            title=f"Paste by {ctx.author}", description=url
        )

        embed.set_thumbnail(url=self.CLIPBOARD_ICON_URL)

        return embed

    async def handle_string_alert(self, config, ctx, content, filter_config):
        if filter_config.warn:
            await self.handle_warn(ctx, ctx.author, filter_config.message)

        if filter_config.delete:
            await ctx.message.delete()
            await self.send_default_delete_response(
                config, ctx, content, filter_config.message
            )
        else:
            await self.bot.send_with_mention(ctx, filter_config.message)

        await self.send_admin_alert(
            config,
            ctx,
            f"Message contained trigger: `{filter_config.trigger}`",
        )

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
        description="Purges the current channel's messages based on amount and author criteria",
        usage="@user @another-user ... [number-to-purge (50 by default)]",
    )
    async def purge_amount(
        self, ctx, targets: commands.Greedy[discord.Member], amount: int = 1
    ):
        # dat constant lookup
        targets = (
            set(user.id for user in ctx.message.mentions)
            if ctx.message.mentions
            else None
        )

        if amount <= 0 or amount > 50:
            amount = 50

        def check(message):
            if not targets or message.author.id in targets:
                return True
            return False

        await ctx.channel.purge(limit=amount, check=check)
        await self.bot.send_with_mention(
            ctx,
            f"I finished deleting {amount} messages",
        )

    @purge.command(
        name="duration",
        aliases=["d"],
        brief="Purges messages by duration",
        description="Purges the current channel's messages up to a time based on author criteria",
        usage="@user @another-user ... [duration (minutes)]",
    )
    async def purge_duration(self, ctx, duration_minutes: int):
        timestamp = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=duration_minutes
        )

        await ctx.channel.purge(after=timestamp)
        await self.bot.send_with_mention(
            ctx,
            f"I finished deleting messages up to `{timestamp}` UTC",
        )
