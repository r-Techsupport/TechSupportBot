"""Module for the protect extension of the discord bot."""

from __future__ import annotations

import datetime
import io
import re
from datetime import timedelta
from typing import TYPE_CHECKING, Self

import dateparser
import discord
import expiringdict
import munch
import ui
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the ChatGPT plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

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


class Protector(cogs.MatchCog):
    """Class for the protector command.

    Attrs:
        ALERT_ICON_URL (str): The icon for the alert messages
        CLIPBOARD_ICON_URL (str): The icon for the paste messages
        CHARS_PER_NEWLINE (int): The arbitrary length of a line

    """

    ALERT_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/2063/PNG/512/"
        + "alert_danger_warning_notification_icon_124692.png"
    )
    CLIPBOARD_ICON_URL = (
        "https://icon-icons.com/icons2/203/PNG/128/diagram-30_24487.png"
    )
    CHARS_PER_NEWLINE = 80

    async def preconfig(self: Self) -> None:
        """Method to preconfig the protect."""
        self.string_alert_cache = expiringdict.ExpiringDict(
            max_len=100, max_age_seconds=3600
        )

    async def match(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> bool:
        """Checks if the message could be triggered by any protect rules
        Checks for channel and that the user isn't exempt

        Args:
            config (munch.Munch): The guild config where the message was sent
            ctx (commands.Context): The context in which the command was run in
            content (str): The string content of the message sent

        Returns:
            bool: False if the message shouldn't be checked, True if it should
        """
        # exit the match based on exclusion parameters
        if not str(ctx.channel.id) in config.extensions.protect.channels.value:
            await self.bot.logger.send_log(
                message="Channel not in protected channels - ignoring protect check",
                level=LogLevel.DEBUG,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
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
    async def on_raw_message_edit(
        self: Self, payload: discord.RawMessageUpdateEvent
    ) -> None:
        """This is called when any message is edited in any guild the bot is in.
        There is no guarantee that the message exists or is used

        Args:
            payload (discord.RawMessageUpdateEvent): The raw event that the edit generated
        """
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        config = self.bot.guild_configs[str(guild.id)]
        if not self.extension_enabled(config):
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message:
            return

        # Don't trigger if content hasn't changed
        if payload.cached_message and payload.cached_message.content == message.content:
            return

        ctx = await self.bot.get_context(message)
        matched = await self.match(config, ctx, message.content)
        if not matched:
            return

        await self.response(config, ctx, message.content, None)

    def search_by_text_regex(
        self: Self, config: munch.Munch, content: str
    ) -> munch.Munch:
        """Searches a given message for static text and regex rule violations

        Args:
            config (munch.Munch): The guild config where the message was sent
            content (str): The string contents of the message that might be filtered

        Returns:
            munch.Munch: The most aggressive filter that is triggered
        """
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
                        return triggered_config
            else:
                if filter_config.get("sensitive"):
                    search_keyword = search_keyword.lower()
                    search_content = search_content.lower()
                if search_keyword in search_content:
                    filter_config["trigger"] = keyword
                    triggered_config = filter_config
                    if triggered_config.get("delete"):
                        return triggered_config
        return triggered_config

    async def response(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str, _: bool
    ) -> None:
        """Checks if a message does violate any set automod rules

        Args:
            config (munch.Munch): The guild config where the message was sent
            ctx (commands.Context): The context of the original message
            content (str): The string content of the message sent
        """
        # check mass mentions first - return after handling
        if len(ctx.message.mentions) > config.extensions.protect.max_mentions.value:
            await self.handle_mass_mention_alert(config, ctx, content)
            return

        # search the message against keyword strings
        triggered_config = self.search_by_text_regex(config, content)

        for attachment in ctx.message.attachments:
            if (
                attachment.filename.split(".")[-1]
                in config.extensions.protect.banned_file_extensions.value
            ):
                await self.handle_file_extension_alert(config, ctx, attachment.filename)
                return

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

    def max_newlines(self: Self, max_length: int) -> int:
        """Gets a theoretical maximum number of new lines in a given message

        Args:
            max_length (int): The max length of characters per theoretical line

        Returns:
            int: The maximum number of new lines based on config
        """
        return int(max_length / self.CHARS_PER_NEWLINE) + 1

    async def handle_length_alert(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> None:
        """Moves message into a linx paste if it's too long

        Args:
            config (munch.Munch): The guild config where the too long message was sent
            ctx (commands.Context): The context where the original message was sent
            content (str): The string content of the flagged message
        """
        attachments: list[discord.File] = []
        if ctx.message.attachments:
            total_attachment_size = 0
            for attch in ctx.message.attachments:
                if (
                    total_attachment_size := total_attachment_size + attch.size
                ) <= ctx.filesize_limit:
                    attachments.append(await attch.to_file())
            if (lf := len(ctx.message.attachments) - len(attachments)) != 0:
                log_channel = config.get("logging_channel")
                await self.bot.logger.send_log(
                    message=(
                        f"Protect did not reupload {lf} file(s) due to file size limit."
                    ),
                    level=LogLevel.WARN,
                    channel=log_channel,
                    context=LogContext(guild=ctx.guild, channel=ctx.channel),
                )
        await ctx.message.delete()

        reason = "message too long (too many newlines or characters)"

        if not self.bot.file_config.api.api_url.linx:
            await self.send_default_delete_response(config, ctx, content, reason)
            return

        linx_embed = await self.create_linx_embed(config, ctx, content)
        if not linx_embed:
            await self.send_default_delete_response(config, ctx, content, reason)
            await self.send_alert(config, ctx, "Could not convert text to Linx paste")
            return

        await ctx.send(
            ctx.message.author.mention, embed=linx_embed, files=attachments[:10]
        )

    async def handle_mass_mention_alert(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> None:
        """Handles a mass mention alert from automod

        Args:
            config (munch.Munch): The guild config where the message was sent
            ctx (commands.Context): The context where the message was sent
            content (str): The string content of the message
        """
        await ctx.message.delete()
        await self.handle_warn(ctx, ctx.author, "mass mention", bypass=True)
        await self.send_alert(config, ctx, f"Mass mentions from {ctx.author}")

    async def handle_file_extension_alert(
        self: Self, config: munch.Munch, ctx: commands.Context, filename: str
    ) -> None:
        """Handles a suspicous file extension flag from automod

        Args:
            config (munch.Munch): The guild config from where the message was sent
            ctx (commands.Context): The context where the message was sent
            filename (str): The filename of the suspicious file that was uploaded
        """
        await ctx.message.delete()
        await self.handle_warn(
            ctx, ctx.author, "Suspicious file extension", bypass=True
        )
        await self.send_alert(
            config, ctx, f"Suspicious file uploaded by {ctx.author}: {filename}"
        )

    async def handle_string_alert(
        self: Self,
        config: munch.Munch,
        ctx: commands.Context,
        content: str,
        filter_config: munch.Munch,
    ) -> None:
        """Handles a static string alert. Is given a rule that was violated

        Args:
            config (munch.Munch): The guild config where the message was sent
            ctx (commands.Context): The context where the original message was sent
            content (str): The string content of the message
            filter_config (munch.Munch): The rule that was triggered by the message
        """
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
            embed = auxiliary.generate_basic_embed(
                title="Chat Protection",
                description=filter_config.message,
                color=discord.Color.gold(),
            )
            await ctx.send(ctx.message.author.mention, embed=embed)

        await self.send_alert(
            config,
            ctx,
            f"Message contained trigger: {filter_config.trigger}",
        )

    async def handle_warn(
        self: Self,
        ctx: commands.Context,
        user: discord.Member,
        reason: str,
        bypass: bool = False,
    ) -> None:
        """Handles the logic of a warning

        Args:
            ctx (commands.Context): The context that generated the warning
            user (discord.Member): The member to warn
            reason (str): The reason for warning
            bypass (bool, optional): If this should bypass the confirmation check.
                Defaults to False.
        """
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
            if not ctx.channel.permissions_for(user).view_channel:
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

    async def handle_unwarn(
        self: Self,
        ctx: commands.Context,
        user: discord.Member,
        reason: str,
        bypass: bool = False,
    ) -> None:
        """Handles the logic of clearing all warnings

        Args:
            ctx (commands.Context): The context that generated theis unwarn
            user (discord.Member): The member to remove warnings from
            reason (str): The reason for clearing warnings
            bypass (bool, optional): If this should bypass the confirmation check.
                Defaults to False.
        """
        # Always allow admins to unwarn other admins
        if not bypass and not ctx.message.author.guild_permissions.administrator:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        warnings = await self.get_warnings(user, ctx.guild)
        if not warnings:
            await auxiliary.send_deny_embed(
                message="There are no warnings for that user", channel=ctx.channel
            )
            return

        await self.clear_warnings(user, ctx.guild)

        embed = await self.generate_user_modified_embed(user, "unwarn", reason)
        await ctx.send(embed=embed)

    async def handle_ban(
        self: Self,
        ctx: commands.Context,
        user: discord.User | discord.Member,
        reason: str,
        bypass: bool = False,
    ) -> None:
        """Handles the logic of banning a user. Is not a discord command

        Args:
            ctx (commands.Context): The context that generated the need for a bad
            user (discord.User | discord.Member): The user or member to be banned
            reason (str): The ban reason to be stored in discord
            bypass (bool, optional): True will ignore permission chekcks. Defaults to False.
        """
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        async for ban in ctx.guild.bans(limit=None):
            if user == ban.user:
                await auxiliary.send_deny_embed(
                    message="User is already banned.", channel=ctx.channel
                )
                return

        config = self.bot.guild_configs[str(ctx.guild.id)]
        await ctx.guild.ban(
            user,
            reason=reason,
            delete_message_days=config.extensions.protect.ban_delete_duration.value,
        )

        embed = await self.generate_user_modified_embed(user, "ban", reason)

        await ctx.send(embed=embed)

    async def handle_unban(
        self: Self,
        ctx: commands.Context,
        user: discord.User,
        reason: str,
        bypass: bool = False,
    ) -> None:
        """Handles the logic of unbanning a user. Is not a discord command

        Args:
            ctx (commands.Context): The context that generated the need for the unban
            user (discord.User): The user to be unbanned
            reason (str): The unban reason to be saved in the audit log
            bypass (bool, optional): True will ignore permission chekcks. Defaults to False.
        """
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        try:
            await ctx.guild.unban(user, reason=reason)
        except discord.NotFound:
            await auxiliary.send_deny_embed(
                message="This user is not banned, or does not exist",
                channel=ctx.channel,
            )
            return

        embed = await self.generate_user_modified_embed(user, "unban", reason)

        await ctx.send(embed=embed)

    async def handle_kick(
        self: Self,
        ctx: commands.Context,
        user: discord.Member,
        reason: str,
        bypass: bool = False,
    ) -> None:
        """Handles the logic of kicking a user. Is not a discord command

        Args:
            ctx (commands.Context): The context that generated the need for the kick
            user (discord.Member): The user to be kicked
            reason (str): The kick reason to be saved in the audit log
            bypass (bool, optional): True will ignore permission chekcks. Defaults to False.
        """
        if not bypass:
            can_execute = await self.can_execute(ctx, user)
            if not can_execute:
                return

        await ctx.guild.kick(user, reason=reason)

        embed = await self.generate_user_modified_embed(user, "kick", reason)

        await ctx.send(embed=embed)

    async def clear_warnings(
        self: Self, user: discord.User | discord.Member, guild: discord.Guild
    ) -> None:
        """This clears all warnings for a given user

        Args:
            user (discord.User | discord.Member): The user or member to wipe all warnings for
            guild (discord.Guild): The guild to clear warning from
        """
        await self.bot.models.Warning.delete.where(
            self.bot.models.Warning.user_id == str(user.id)
        ).where(self.bot.models.Warning.guild_id == str(guild.id)).gino.status()

    async def generate_user_modified_embed(
        self: Self, user: discord.User | discord.Member, action: str, reason: str
    ) -> discord.Embed:
        """This generates an embed to be shown to the user on why their message was actioned

        Args:
            user (discord.User | discord.Member): The user or member who was punished
            action (str): The action that was taken against the person
            reason (str): The reason for the action taken

        Returns:
            discord.Embed: The prepared embed ready to be sent
        """
        embed = discord.Embed(
            title="Chat Protection", description=f"{action.upper()} `{user}`"
        )
        embed.set_footer(text=f"Reason: {reason}")
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.color = discord.Color.gold()

        return embed

    def get_cache_key(
        self: Self, guild: discord.Guild, user: discord.Member, trigger: str
    ) -> str:
        """Gets the cache key for repeated automod triggers

        Args:
            guild (discord.Guild): The guild where the trigger has occured
            user (discord.Member): The member that triggered the automod
            trigger (str): The string representation of the automod rule that triggered

        Returns:
            str: The key to lookup the cache entry, if it exists
        """
        return f"{guild.id}_{user.id}_{trigger}"

    async def can_execute(
        self: Self, ctx: commands.Context, target: discord.User | discord.Member
    ) -> bool:
        """Checks permissions to determine if the protect command should execute.
        This checks:
        - If the executer is the same as the target
        - If the target is a bot
        - If the member is immune to protect
        - If the bot doesn't have permissions
        - If the user wouldn't have permissions based on their roles

        Args:
            ctx (commands.Context): The context that required the need for moderative action
            target (discord.User | discord.Member): The target of the moderative action

        Returns:
            bool: True if the executer can execute this command, False if they can't
        """
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

    async def send_alert(
        self: Self, config: munch.Munch, ctx: commands.Context, message: str
    ) -> None:
        """Sends a protect alert to the protect events channel to alert the mods

        Args:
            config (munch.Munch): The guild config in the guild where the event occured
            ctx (commands.Context): The context that generated this alert
            message (str): The message to send to the mods about the alert
        """
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

    async def send_default_delete_response(
        self: Self,
        config: munch.Munch,
        ctx: commands.Context,
        content: str,
        reason: str,
    ) -> None:
        """Sends a DM to a user containing a message that was deleted

        Args:
            config (munch.Munch): The config of the guild where the message was sent
            ctx (commands.Context): The context of the deleted message
            content (str): The context of the deleted message
            reason (str): The reason the message was deleted
        """
        embed = auxiliary.generate_basic_embed(
            title="Chat Protection",
            description=f"Message deleted. Reason: *{reason}*",
            color=discord.Color.gold(),
        )
        await ctx.send(ctx.message.author.mention, embed=embed)
        await ctx.author.send(f"Deleted message: ```{content[:1994]}```")

    async def get_warnings(
        self: Self, user: discord.Member | discord.User, guild: discord.Guild
    ) -> list[bot.models.Warning]:
        """Gets a list of every warning for a given user

        Args:
            user (discord.Member | discord.User): The user or member object to lookup warnings for
            guild (discord.Guild): The guild to get the warnings for

        Returns:
            list[bot.models.Warning]: The list of all warnings that
                user or member has in the given guild
        """
        warnings = (
            await self.bot.models.Warning.query.where(
                self.bot.models.Warning.user_id == str(user.id)
            )
            .where(self.bot.models.Warning.guild_id == str(guild.id))
            .gino.all()
        )
        return warnings

    async def create_linx_embed(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> discord.Embed | None:
        """This function sends a message to the linx url and puts the result in
        an embed to be sent to the user

        Args:
            config (munch.Munch): The guild config where the message was sent
            ctx (commands.Context): The context that generated the need for a paste
            content (str): The context of the message to be pasted

        Returns:
            discord.Embed | None: The formatted embed, or None if there was an API error
        """
        if not content:
            return None

        headers = {
            "Linx-Expiry": "1800",
            "Linx-Randomize": "yes",
            "Accept": "application/json",
        }
        file_to_paste = {"file": io.StringIO(content)}
        response = await self.bot.http_functions.http_call(
            "post",
            self.bot.file_config.api.api_url.linx,
            headers=headers,
            data=file_to_paste,
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
        embed.set_footer(text=config.extensions.protect.paste_footer_message.value)
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
    async def ban_user(
        self: Self, ctx: commands.Context, user: discord.User, *, reason: str = None
    ) -> None:
        """The ban discord command, starts the process of banning a user

        Args:
            ctx (commands.Context): The context that called this command
            user (discord.User): The user that is going to be banned
            reason (str, optional): The reason for the ban. Defaults to None.
        """

        # Uses the discord.Member class to get the top role attribute if the
        # user is a part of the target guild
        if ctx.guild.get_member(user.id) is not None:
            await self.handle_ban(ctx, ctx.guild.get_member(user.id), reason)
        else:
            await self.handle_ban(ctx, user, reason)

        config = self.bot.guild_configs[str(ctx.guild.id)]
        await self.send_alert(config, ctx, "Ban command")

    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.command(
        name="unban",
        brief="Unbans a user",
        description="Unbans a user with a given reason",
        usage="@user [reason]",
    )
    async def unban_user(
        self: Self, ctx: commands.Context, user: discord.User, *, reason: str = None
    ) -> None:
        """The unban discord command, starts the process of unbanning a user

        Args:
            ctx (commands.Context): The context that called this command
            user (discord.User): The user that is going to be unbanned
            reason (str, optional): The reason for the unban. Defaults to None.
        """

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
    async def kick_user(
        self: Self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ) -> None:
        """The kick discord command, starts the process of kicking a user

        Args:
            ctx (commands.Context): The context that called this command
            user (discord.Member): The user that is going to be kicked
            reason (str, optional): The reason for the kick. Defaults to None.
        """
        await self.handle_kick(ctx, user, reason)

        config = self.bot.guild_configs[str(ctx.guild.id)]
        await self.send_alert(config, ctx, "Kick command")

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="warn",
        brief="Warns a user",
        description="Warn a user with a given reason",
        usage="@user [reason]",
    )
    async def warn_user(
        self: Self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ) -> None:
        """The warn discord command, starts the process of warning a user

        Args:
            ctx (commands.Context): The context that called this command
            user (discord.Member): The user that is going to be warned
            reason (str, optional): The reason for the warn. Defaults to None.
        """
        await self.handle_warn(ctx, user, reason)

        config = self.bot.guild_configs[str(ctx.guild.id)]
        await self.send_alert(config, ctx, "Warn command")

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="unwarn",
        brief="Unwarns a user",
        description="Unwarns a user with a given reason",
        usage="@user [reason]",
    )
    async def unwarn_user(
        self: Self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ) -> None:
        """The unwarn discord command, starts the process of unwarning a user
        This clears ALL warnings from a member

        Args:
            ctx (commands.Context): The context that called this command
            user (discord.Member): The user that is going to be unwarned
            reason (str, optional): The reason for the unwarn. Defaults to None.
        """
        await self.handle_unwarn(ctx, user, reason)

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="warnings",
        brief="Gets warnings",
        description="Gets warnings for a user",
        usage="@user",
    )
    async def get_warnings_command(
        self: Self, ctx: commands.Context, user: discord.User
    ) -> None:
        """Displays all warnings that a given user has

        Args:
            ctx (commands.Context): The context that called this command
            user (discord.User): The user to get warnings for
        """
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

    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.command(
        name="mute",
        brief="Mutes a user",
        description="Times out a user for the specified duration",
        usage="@user [time] [reason]",
        aliases=["timeout"],
    )
    async def mute(
        self: Self, ctx: commands.Context, user: discord.Member, *, duration: str = None
    ) -> None:
        """Method to mute a user in discord using the native timeout.
        This should be run via discord

        Args:
            ctx (commands.Context): The context that was generated by running this command
            user (discord.Member): The discord.Member to be timed out.
            duration (str, optional): Max time is 28 days by discord API. Defaults to 1 hour

        Raises:
            ValueError: Raised if the provided duration string cannot be converted into a time
        """

        can_execute = await self.can_execute(ctx, user)
        if not can_execute:
            return

        # The API prevents administrators from being timed out. Check it here
        if user.guild_permissions.administrator:
            await auxiliary.send_deny_embed(
                message=(
                    "Someone with the `administrator` permissions cannot be timed out"
                ),
                channel=ctx.channel,
            )
            return

        delta_duration = None

        if duration:
            # The date parser defaults to time in the past, so it is second
            # This could be fixed by appending "in" to your query, but this is simpler
            try:
                delta_duration = datetime.datetime.now() - dateparser.parse(duration)
                delta_duration = timedelta(
                    seconds=round(delta_duration.total_seconds())
                )
            except TypeError as exc:
                raise ValueError("Invalid duration") from exc
            if not delta_duration:
                raise ValueError("Invalid duration")
        else:
            delta_duration = timedelta(hours=1)

        # Checks to ensure time is valid and within the scope of the API
        if delta_duration > timedelta(days=28):
            raise ValueError("Timeout duration cannot be more than 28 days")
        if delta_duration < timedelta(seconds=1):
            raise ValueError("Timeout duration cannot be less than 1 second")

        # Timeout the user and send messages to both the invocation channel, and the protect log
        await user.timeout(delta_duration)

        embed = await self.generate_user_modified_embed(
            user, f"muted for {delta_duration}", reason=None
        )

        await ctx.send(embed=embed)

        config = self.bot.guild_configs[str(ctx.guild.id)]
        await self.send_alert(config, ctx, "Mute command")

    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.command(
        name="unmute",
        brief="Unutes a user",
        description="Removes a timeout from the user",
        usage="@user",
        aliases=["untimeout"],
    )
    async def unmute(
        self: Self, ctx: commands.Context, user: discord.Member, reason: str = None
    ) -> None:
        """Method to mute a user in discord using the native timeout.
        This should be run via discord

        Args:
            ctx (commands.Context): The context that was generated by running this command
            user (discord.Member): The discord.Member to have mute be cleared.
            reason (str, optional): The reason for the unmute. Defaults to None.
        """
        can_execute = await self.can_execute(ctx, user)
        if not can_execute:
            return

        if user.timed_out_until is None:
            await auxiliary.send_deny_embed(
                message="That user is not timed out", channel=ctx.channel
            )
            return

        await user.timeout(None)

        embed = await self.generate_user_modified_embed(user, "unmuted", reason)

        await ctx.send(embed=embed)

    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.group(
        brief="Executes a purge command",
        description="Executes a purge command",
    )
    async def purge(self: Self, ctx: commands.Context) -> None:
        """The bare .purge command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @purge.command(
        name="amount",
        aliases=["x"],
        brief="Purges messages by amount",
        description="Purges the current channel's messages based on amount",
        usage="[amount]",
    )
    async def purge_amount(self: Self, ctx: commands.Context, amount: int = 1) -> None:
        """Purges the most recent amount+1 messages in the channel the command was run in

        Args:
            ctx (commands.Context): The context that called the command
            amount (int, optional): The amount of messages to purge. Defaults to 1.
        """
        config = self.bot.guild_configs[str(ctx.guild.id)]

        if amount <= 0 or amount > config.extensions.protect.max_purge_amount.value:
            amount = config.extensions.protect.max_purge_amount.value

        await ctx.channel.purge(limit=amount + 1)

        await self.send_alert(config, ctx, "Purge command")

    @purge.command(
        name="duration",
        aliases=["d"],
        brief="Purges messages by duration",
        description="Purges the current channel's messages up to a time",
        usage="[duration (minutes)]",
    )
    async def purge_duration(
        self: Self, ctx: commands.Context, duration_minutes: int
    ) -> None:
        """Purges the most recent duration_minutes worth of messages in the
            channel the command was run in

        Args:
            ctx (commands.Context): The context that called the command
            duration_minutes (int): The amount of minutes to purge away
        """
        if duration_minutes < 0:
            await auxiliary.send_deny_embed(
                message="I can't use that input", channel=ctx.channel
            )
            return

        timestamp = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=duration_minutes
        )

        config = self.bot.guild_configs[str(ctx.guild.id)]

        await ctx.channel.purge(
            after=timestamp, limit=config.extensions.protect.max_purge_amount.value
        )

        await self.send_alert(config, ctx, "Purge command")
