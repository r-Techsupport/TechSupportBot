"""
Todo:
    Purge to slash commands
    Unwarn has autofill
    Get all warnings command
    
    Make all of automod
    Simplify paste
    Make paste not work if message would be DELETED by automod
    Create a ban logging system like carl - Needs a database for ban history
        Central unban logging but NO database needed

Ban logs need to be more centralized:
    Auto bans, command bans, and manual bans all need to be logged with a single message
    A modlog highscores command, in a modlog.py command

Move all config over to specific new files
"""

import discord
import expiringdict
import ui
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands


async def setup(bot):
    """Class to set up the protect options in the config file."""

    config = extensionconfig.ExtensionConfig()
    config.add(
        key="channels",
        datatype="list",
        title="Protected channels",
        description=(
            "The list of channel ID's associated with the channels to auto-protect"
        ),
        default=[],
    )
    config.add(
        key="bypass_roles",
        datatype="list",
        title="Bypassed role names",
        description=(
            "The list of role names associated with bypassed roles by the auto-protect"
        ),
        default=[],
    )
    config.add(
        key="immune_roles",
        datatype="list",
        title="Immune role names",
        description="The list of role names that are immune to protect commands",
        default=[],
    )
    config.add(
        key="bypass_ids",
        datatype="list",
        title="Bypassed member ID's",
        description=(
            "The list of member ID's associated with bypassed members by the"
            " auto-protect"
        ),
        default=[],
    )
    config.add(
        key="length_limit",
        datatype="int",
        title="Max length limit",
        description=(
            "The max char limit on messages before they trigger an action by"
            " auto-protect"
        ),
        default=500,
    )
    config.add(
        key="string_map",
        datatype="dict",
        title="Keyword string map",
        description=(
            "Mapping of keyword strings to data defining the action taken by"
            " auto-protect"
        ),
        default={},
    )
    config.add(
        key="banned_file_extensions",
        datatype="dict",
        title="List of banned file types",
        description=(
            "A list of all file extensions to be blocked and have a auto warning issued"
        ),
        default=[],
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
        description=(
            "Max number of mentions allowed in a message before triggering auto-protect"
        ),
        default=3,
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
        description=(
            "The amount of days to delete messages for a user after they are banned"
        ),
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
        key="paste_footer_message",
        datatype="str",
        title="The linx embed footer",
        description="The message used on the footer of the large message paste URL",
        default="Note: Long messages are automatically pasted",
    )

    await bot.add_cog(Protector(bot=bot, extension_name="protect"))
    bot.add_extension_config("protect", config)


class ProtectEmbed(discord.Embed):
    """Class to make the embed for the protect command."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "Chat Protection"
        self.color = discord.Color.gold()


class Protector(cogs.MatchCog):
    """Class for the protector command."""

    ALERT_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/2063/PNG/512/"
        + "alert_danger_warning_notification_icon_124692.png"
    )
    CLIPBOARD_ICON_URL = (
        "https://icon-icons.com/icons2/203/PNG/128/diagram-30_24487.png"
    )

    async def preconfig(self):
        """Method to preconfig the protect."""
        self.string_alert_cache = expiringdict.ExpiringDict(
            max_len=100, max_age_seconds=3600
        )

    async def handle_string_alert(self, config, ctx, content, filter_config):
        """Method to handle a string alert for the protect extension."""
        # If needed, delete the message
        if filter_config.delete:
            await ctx.message.delete()

        # Send only 1 response based on warn, deletion, or neither
        if filter_config.warn:
            await self.handle_warn(ctx, ctx.author, filter_config.message, bypass=True)
        elif filter_config.delete:
            await self.send_default_delete_response(
                config, ctx, content, filter_config.message
            )
        else:
            # Ensure we don't trigger people more than once if the only trigger is a warning
            cache_key = self.get_cache_key(ctx.guild, ctx.author, filter_config.trigger)
            if self.string_alert_cache.get(cache_key):
                return

            self.string_alert_cache[cache_key] = True
            embed = ProtectEmbed(description=filter_config.message)
            await ctx.send(ctx.message.author.mention, embed=embed)

        await self.send_alert(
            config,
            ctx,
            f"Message contained trigger: {filter_config.trigger}",
        )

    async def handle_warn(self, ctx, user: discord.Member, reason: str, bypass=False):
        """Method to handle the warn of a user."""
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        warnings = await self.get_warnings(user, ctx.guild)

        new_count = len(warnings) + 1

        config = self.bot.guild_configs[str(ctx.guild.id)]

        if new_count >= config.extensions.protect.max_warnings.value:
            # Start by assuming we don't want to ban someone
            should_ban = False

            # If there is no bypass, ask using ui.Confirm
            # If there is a bypass, assume we want to ban
            if not bypass:
                view = ui.Confirm()
                await view.send(
                    message="This user has exceeded the max warnings of "
                    + f"{config.extensions.protect.max_warnings.value}. Would "
                    + "you like to ban them instead?",
                    channel=ctx.channel,
                    author=ctx.author,
                )
                await view.wait()
                if view.value is ui.ConfirmResponse.CONFIRMED:
                    should_ban = True
            else:
                should_ban = True

            if should_ban:
                await self.handle_ban(
                    ctx,
                    user,
                    f"Over max warning count {new_count} out "
                    + f"of {config.extensions.protect.max_warnings.value}"
                    + f" (final warning: {reason})",
                    bypass=True,
                )
                await self.clear_warnings(user, ctx.guild)
                return

        embed = await self.generate_user_modified_embed(
            user, "warn", f"{reason} ({new_count} total warnings)"
        )

        # Attempt DM for manually initiated, non-banning warns
        if ctx.command == self.bot.get_command("warn"):
            # Cancel warns in channels invisible to user
            if user not in ctx.channel.members:
                await auxiliary.send_deny_embed(
                    message=f"{user} cannot see this warning.", channel=ctx.channel
                )
                return

            try:
                await user.send(embed=embed)

            except (discord.HTTPException, discord.Forbidden):
                channel = config.get("logging_channel")
                await self.bot.logger.send_log(
                    message=f"Failed to DM warning to {user}",
                    level=LogLevel.WARNING,
                    channel=channel,
                    context=LogContext(guild=ctx.guild, channel=ctx.channel),
                )

            finally:
                await ctx.send(content=user.mention, embed=embed)

        else:
            await ctx.send(ctx.message.author.mention, embed=embed)

        await self.bot.models.Warning(
            user_id=str(user.id), guild_id=str(ctx.guild.id), reason=reason
        ).create()

    async def clear_warnings(self, user, guild):
        """Method to clear warnings of a user in discord."""
        await self.bot.models.Warning.delete.where(
            self.bot.models.Warning.user_id == str(user.id)
        ).where(self.bot.models.Warning.guild_id == str(guild.id)).gino.status()

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

    async def can_execute(self, ctx: commands.Context, target: discord.User):
        """Method to not execute on admin users."""
        action = ctx.command.name or "do that to"
        config = self.bot.guild_configs[str(ctx.guild.id)]

        # Check to see if executed on author
        if target == ctx.author:
            await auxiliary.send_deny_embed(
                message=f"You cannot {action} yourself", channel=ctx.channel
            )
            return False
        # Check to see if executed on bot
        if target == self.bot.user:
            await auxiliary.send_deny_embed(
                message=f"It would be silly to {action} myself", channel=ctx.channel
            )
            return False
        # Check to see if target has a role. Will allow execution on Users outside of server
        if not hasattr(target, "top_role"):
            return True
        # Check to see if target has any immune roles
        for name in config.extensions.protect.immune_roles.value:
            role_check = discord.utils.get(target.guild.roles, name=name)
            if role_check and role_check in getattr(target, "roles", []):
                await auxiliary.send_deny_embed(
                    message=(
                        f"You cannot {action} {target} because they have `{role_check}`"
                        " role"
                    ),
                    channel=ctx.channel,
                )
                return False
        # Check to see if the Bot can execute on the target
        if ctx.guild.me.top_role <= target.top_role:
            await auxiliary.send_deny_embed(
                message=f"Bot does not have enough permissions to {action} `{target}`",
                channel=ctx.channel,
            )
            return False
        # Check to see if author top role is higher than targets
        if target.top_role >= ctx.author.top_role:
            await auxiliary.send_deny_embed(
                message=f"You do not have enough permissions to {action} `{target}`",
                channel=ctx.channel,
            )
            return False
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
        await ctx.send(ctx.message.author.mention, embed=embed)
        await ctx.author.send(f"Deleted message: ```{content[:1994]}```")

    async def get_warnings(self, user, guild):
        """Method to get the warnings of a user."""
        warnings = (
            await self.bot.models.Warning.query.where(
                self.bot.models.Warning.user_id == str(user.id)
            )
            .where(self.bot.models.Warning.guild_id == str(guild.id))
            .gino.all()
        )
        return warnings

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
            await auxiliary.send_deny_embed(
                message="There are no warnings for that user", channel=ctx.channel
            )
            return

        embed = discord.Embed(title=f"Warnings for {user}")
        for warning in warnings:
            embed.add_field(name=warning.time, value=warning.reason, inline=False)

        embed.set_thumbnail(url=user.display_avatar.url)

        embed.color = discord.Color.red()

        await ctx.send(embed=embed)
