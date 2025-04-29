"""Manual moderation commands and helper functions"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Self

import dateparser
import discord
import ui
from botlogging import LogContext, LogLevel
from commands import modlog
from core import auxiliary, cogs, extensionconfig, moderation
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="immune_roles",
        datatype="list",
        title="Immune role names",
        description="The list of role names that are immune to protect commands",
        default=[],
    )
    config.add(
        key="ban_delete_duration",
        datatype="int",
        title="Ban delete duration (days)",
        description=(
            "The default amount of days to delete messages for a user after they are banned"
        ),
        default=7,
    )
    await bot.add_cog(ProtectCommands(bot=bot, extension_name="moderator"))
    bot.add_extension_config("moderator", config)


class ProtectCommands(cogs.BaseCog):
    """The cog for all manual moderation activities
    These are all slash commands

    Attributes:
        warnings_group (app_commands.Group): The group for the /warning commands
    """

    warnings_group: app_commands.Group = app_commands.Group(
        name="warning", description="...", extras={"module": "moderator"}
    )

    # Commands

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.command(
        name="ban",
        description="Bans a user from the guild",
        extras={"module": "moderator"},
    )
    async def handle_ban_user(
        self: Self,
        interaction: discord.Interaction,
        target: discord.User,
        reason: str,
        delete_days: app_commands.Range[int, 0, 7] = None,
    ) -> None:
        """The ban slash command. This checks that the permissions are correct
        and that the user is not already banned

        Args:
            interaction (discord.Interaction): The interaction that called this command
            target (discord.User): The target to ban
            reason (str): The reason the person is getting banned
            delete_days (app_commands.Range[int, 0, 7], optional): How many days of
                messages to delete. Defaults to None.
        """
        # Ensure we can ban the person
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="ban"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        if len(reason) > 500:
            embed = auxiliary.prepare_deny_embed(
                message="Ban reason must be under 500 characters"
            )
            await interaction.response.send_message(embed=embed)

        is_banned = await moderation.check_if_user_banned(target, interaction.guild)
        if is_banned:
            embed = auxiliary.prepare_deny_embed(message="User is already banned.")
            await interaction.response.send_message(embed=embed)
            return

        if not delete_days:
            config = self.bot.guild_configs[str(interaction.guild.id)]
            delete_days = config.extensions.moderator.ban_delete_duration.value

        # Ban the user using the core moderation cog
        result = await moderation.ban_user(
            guild=interaction.guild,
            user=target,
            delete_seconds=delete_days * 86400,
            reason=f"{reason} - banned by {interaction.user}",
        )
        if not result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when banning {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        await modlog.log_ban(
            self.bot, target, interaction.user, interaction.guild, reason
        )

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=(
                f"/ban target: {target.display_name}, reason: {reason}, delete_days:"
                f" {delete_days}"
            ),
            guild=interaction.guild,
            target=target,
        )
        embed = generate_response_embed(user=target, action="ban", reason=reason)
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.command(
        name="unban",
        description="Unbans a user from the guild",
        extras={"module": "moderator"},
    )
    async def handle_unban_user(
        self: Self, interaction: discord.Interaction, target: discord.User, reason: str
    ) -> None:
        """The logic for the /unban command

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            target (discord.User): The target to be unbanned
            reason (str): The reason for the user being unbanned
        """
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="unban"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        if len(reason) > 500:
            embed = auxiliary.prepare_deny_embed(
                message="Unban reason must be under 500 characters"
            )
            await interaction.response.send_message(embed=embed)

        is_banned = await moderation.check_if_user_banned(target, interaction.guild)

        if not is_banned:
            embed = auxiliary.prepare_deny_embed(message=f"{target} is not banned")
            await interaction.response.send_message(embed=embed)
            return

        result = await moderation.unban_user(
            guild=interaction.guild,
            user=target,
            reason=f"{reason} - unbanned by {interaction.user}",
        )
        if not result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when unbanning {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        await modlog.log_unban(
            self.bot, target, interaction.user, interaction.guild, reason
        )

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=f"/unban target: {target.display_name}, reason: {reason}",
            guild=interaction.guild,
            target=target,
        )
        embed = generate_response_embed(user=target, action="unban", reason=reason)
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @app_commands.command(
        name="kick",
        description="Kicks a user from the guild",
        extras={"module": "moderator"},
    )
    async def handle_kick_user(
        self: Self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
    ) -> None:
        """The core logic for the /kick command

        Args:
            interaction (discord.Interaction): The interaction that triggered the command
            target (discord.Member): The target for being kicked
            reason (str): The reason for the user being kicked
        """
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="kick"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        if len(reason) > 500:
            embed = auxiliary.prepare_deny_embed(
                message="Reason length is capped at 500 characters"
            )
            await interaction.response.send_message(embed=embed)

        result = await moderation.kick_user(
            guild=interaction.guild,
            user=target,
            reason=f"{reason} - kicked by {interaction.user}",
        )
        if not result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when kicking {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=f"/kick target: {target.display_name}, reason: {reason}",
            guild=interaction.guild,
            target=target,
        )
        embed = generate_response_embed(user=target, action="kick", reason=reason)
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.command(
        name="mute", description="Times out a user", extras={"module": "moderator"}
    )
    async def handle_mute_user(
        self: Self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
        duration: str = None,
    ) -> None:
        """The core logic for the /mute command

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            target (discord.Member): The target for being muted
            reason (str): The reason for being muted
            duration (str, optional): The human readable duration to be muted for. Defaults to None.

        Raises:
            ValueError: Raised if the duration is invalid or cannot be parsed
        """
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="mute"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        if len(reason) > 500:
            embed = auxiliary.prepare_deny_embed(
                message="Mute reason must be below 500 characters"
            )
            await interaction.response.send_message(embed=embed)

        # The API prevents administrators from being timed out. Check it here
        if target.guild_permissions.administrator:
            embed = auxiliary.prepare_deny_embed(
                message=(
                    "Someone with the `administrator` permissions cannot be timed out"
                )
            )
            await interaction.response.send_message(embed=embed)
            return

        delta_duration = None

        if duration:
            # The date parser defaults to time in the past, so it is second
            # This could be fixed by appending "in" to your query, but this is simpler
            try:
                delta_duration = datetime.now() - dateparser.parse(duration)
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

        result = await moderation.mute_user(
            user=target,
            reason=f"{reason} - muted by {interaction.user}",
            duration=delta_duration,
        )
        if not result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when muting {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=(
                f"/mute target: {target.display_name}, reason: {reason}, duration:"
                f" {duration}"
            ),
            guild=interaction.guild,
            target=target,
        )

        muted_until_timestamp = (
            f"<t:{int((datetime.now() + delta_duration).timestamp())}>"
        )

        full_reason = f"{reason} (muted until {muted_until_timestamp})"

        embed = generate_response_embed(user=target, action="mute", reason=full_reason)
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.checks.bot_has_permissions(moderate_members=True)
    @app_commands.command(
        name="unmute",
        description="Removes timeout from a user",
        extras={"module": "moderator"},
    )
    async def handle_unmute_user(
        self: Self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
    ) -> None:
        """The core logic for the /unmute command

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            target (discord.Member): The target for being unmuted
            reason (str): The reason for the unmute
        """
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="unmute"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        if len(reason) > 500:
            embed = auxiliary.prepare_deny_embed(
                message="Unmute reason must be below 500 characters"
            )
            await interaction.response.send_message(embed=embed)

        if not target.timed_out_until:
            embed = auxiliary.prepare_deny_embed(
                message=(f"{target} is not currently muted")
            )
            await interaction.response.send_message(embed=embed)
            return

        result = await moderation.unmute_user(
            user=target,
            reason=f"{reason} - unmuted by {interaction.user}",
        )
        if not result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when unmuting {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=f"/unmute target: {target.display_name}, reason: {reason}",
            guild=interaction.guild,
            target=target,
        )
        embed = generate_response_embed(user=target, action="unmute", reason=reason)
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @app_commands.command(
        name="warn", description="Warns a user", extras={"module": "moderator"}
    )
    async def handle_warn_user(
        self: Self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
    ) -> None:
        """The core logic for the /warn command

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            target (discord.Member): The target for being warned
            reason (str): The reason the user is being warned
        """
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="warn"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        if len(reason) > 500:
            embed = auxiliary.prepare_deny_embed(
                message="Warn reason must be below 500 characters"
            )
            await interaction.response.send_message(embed=embed)

        if target not in interaction.channel.members:
            embed = auxiliary.prepare_deny_embed(
                message=f"{target} cannot see this warning. No warning was added."
            )
            await interaction.response.send_message(embed=embed)
            return

        config = self.bot.guild_configs[str(interaction.guild.id)]

        new_count_of_warnings = (
            len(await moderation.get_all_warnings(self.bot, target, interaction.guild))
            + 1
        )

        should_ban = False
        if new_count_of_warnings >= config.moderation.max_warnings:
            await interaction.response.defer(ephemeral=False)
            view = ui.Confirm()
            await view.send(
                message="This user has exceeded the max warnings of "
                + f"{config.moderation.max_warnings}. Would "
                + "you like to ban them instead?",
                channel=interaction.channel,
                author=interaction.user,
                interaction=interaction,
            )
            await view.wait()
            if view.value is ui.ConfirmResponse.CONFIRMED:
                should_ban = True

        warn_result = await moderation.warn_user(
            bot_object=self.bot, user=target, invoker=interaction.user, reason=reason
        )

        if should_ban:
            ban_result = await moderation.ban_user(
                guild=interaction.guild,
                user=target,
                delete_seconds=(
                    config.extensions.moderator.ban_delete_duration.value * 86400
                ),
                reason=(
                    f"Over max warning count {new_count_of_warnings} out of"
                    f" {config.moderation.max_warnings} (final warning:"
                    f" {reason}) - banned by {interaction.user}"
                ),
            )
            if not ban_result:
                embed = auxiliary.prepare_deny_embed(
                    message=f"Something went wrong when banning {target}"
                )
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed)
                return
            await modlog.log_ban(
                self.bot, target, interaction.user, interaction.guild, reason
            )

        if not warn_result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when warning {target}"
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed)
            else:
                await interaction.response.send_message(embed=embed)
            return

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=f"/warn target: {target.display_name}, reason: {reason}",
            guild=interaction.guild,
            target=target,
        )

        embed = generate_response_embed(
            user=target,
            action="warn",
            reason=f"{reason} ({new_count_of_warnings} total warnings)",
        )
        if interaction.response.is_done():
            await interaction.followup.send(content=target.mention, embed=embed)
        else:
            await interaction.response.send_message(content=target.mention, embed=embed)

        try:
            await target.send(embed=embed)
        except (discord.HTTPException, discord.Forbidden):
            channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message=f"Failed to DM warning to {target}",
                level=LogLevel.WARNING,
                channel=channel,
                context=LogContext(
                    guild=interaction.guild, channel=interaction.channel
                ),
            )

    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @app_commands.command(
        name="unwarn", description="Unwarns a user", extras={"module": "moderator"}
    )
    async def handle_unwarn_user(
        self: Self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
        warning: str,
    ) -> None:
        """The core logic of the /unwarn command

        Args:
            interaction (discord.Interaction): The interaction that triggered the command
            target (discord.Member): The user being unwarned
            reason (str): The reason for the unwarn
            warning (str): The exact string of the warning
        """
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="unwarn"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        if len(reason) > 500:
            embed = auxiliary.prepare_deny_embed(
                message="Reason length is capped at 500 characters"
            )
            await interaction.response.send_message(embed=embed)

        database_warning = await self.get_warning(user=target, warning=warning)

        if not database_warning:
            embed = auxiliary.prepare_deny_embed(
                message=f"{warning} was not found on {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        result = await moderation.unwarn_user(
            bot_object=self.bot, user=target, warning=warning
        )
        if not result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when unwarning {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=f"/unwarn target: {target.display_name}, reason: {reason}, warning: {warning}",
            guild=interaction.guild,
            target=target,
        )
        embed = generate_response_embed(user=target, action="unwarn", reason=reason)
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @warnings_group.command(
        name="clear",
        description="clears all warnings from a user",
        extras={"module": "moderator"},
    )
    async def handle_warning_clear(
        self: Self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
    ) -> None:
        """The core logic of the /warnings clear command

        Args:
            interaction (discord.Interaction): The interaction that triggered the command
            target (discord.Member): The user having warnings cleared
            reason (str): The reason for the warnings being cleared
        """
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="unwarn"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        if len(reason) > 500:
            embed = auxiliary.prepare_deny_embed(
                message="Reason must be below 500 characters"
            )
            await interaction.response.send_message(embed=embed)

        warnings = await moderation.get_all_warnings(
            self.bot, target, interaction.guild
        )

        if not warnings:
            embed = auxiliary.prepare_deny_embed(
                message=f"{target} has no warnings"
            )
            await interaction.response.send_message(embed=embed)
            return

        for warning in warnings:
            await moderation.unwarn_user(self.bot, target, warning.reason)

        await moderation.send_command_usage_alert(
            bot_object=self.bot,
            interaction=interaction,
            command=f"/warnings clear target: {target.display_name}, reaason: {reason}",
            guild=interaction.guild,
            target=target,
        )

        embed = generate_response_embed(
            user=target, action="warnings clear", reason=reason
        )
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.checks.bot_has_permissions(kick_members=True)
    @warnings_group.command(
        name="all",
        description="Shows all warnings to the invoker",
        extras={"module": "moderator"},
    )
    async def handle_warning_all(
        self: Self,
        interaction: discord.Interaction,
        target: discord.User,
    ) -> None:
        """The core logic of the /warnings all command

        Args:
            interaction (discord.Interaction): The interaction that triggered the command
            target (discord.User): The user to lookup warnings for
        """
        warnings = await moderation.get_all_warnings(
            self.bot, target, interaction.guild
        )

        embeds = build_warning_embeds(interaction.guild, target, warnings)

        await interaction.response.defer(ephemeral=True)
        view = ui.PaginateView()
        await view.send(
            interaction.channel, interaction.user, embeds, interaction, True
        )

    # Helper functions

    async def permission_check(
        self: Self,
        invoker: discord.Member,
        target: discord.User | discord.Member,
        action_name: str,
    ) -> str:
        """Checks permissions to ensure the command should be executed. This checks:
        If the target is the invoker
        If the target is the bot
        If the user is in the server
        If the target has an immune role
        If the target can be banned by the bot
        If the invoker has a higher role than the target

        Args:
            invoker (discord.Member): The invoker of the action.
                Either will be the user who ran the command, or the bot itself
            target (discord.User | discord.Member): The target of the command.
                Can be a user or member.
            action_name (str): The action name to be displayed in messages

        Returns:
            str: The rejection string, if one exists. Otherwise, None is returned
        """
        config = self.bot.guild_configs[str(invoker.guild.id)]
        # Check to see if executed on author
        if invoker == target:
            return f"You cannot {action_name} yourself"

        # Check to see if executed on bot
        if target == self.bot.user:
            return f"It would be silly to {action_name} myself"

        # Check to see if User or Member
        if isinstance(target, discord.User):
            return None

        # Check to see if target has any immune roles
        for name in config.extensions.moderator.immune_roles.value:
            role_check = discord.utils.get(target.guild.roles, name=name)
            if role_check and role_check in getattr(target, "roles", []):
                return (
                    f"You cannot {action_name} {target} because they have"
                    f" `{role_check}` role"
                )

        # Check to see if the Bot can execute on the target
        if invoker.guild.get_member(int(self.bot.user.id)).top_role <= target.top_role:
            return f"Bot does not have enough permissions to {action_name} `{target}`"

        # Check to see if author top role is higher than targets
        if invoker.top_role <= target.top_role:
            return f"You do not have enough permissions to {action_name} `{target}`"

        return None

    # Database functions

    async def get_warning(
        self: Self, user: discord.Member, warning: str
    ) -> bot.models.Warning:
        """Gets a specific warning by string for a user

        Args:
            user (discord.Member): The user to get the warning for
            warning (str): The warning to look for

        Returns:
            bot.models.Warning: If it exists, the warning object
        """
        query = (
            self.bot.models.Warning.query.where(
                self.bot.models.Warning.guild_id == str(user.guild.id)
            )
            .where(self.bot.models.Warning.reason == warning)
            .where(self.bot.models.Warning.user_id == str(user.id))
        )
        entry = await query.gino.first()
        return entry


def generate_response_embed(
    user: discord.Member, action: str, reason: str
) -> discord.Embed:
    """This generates a simple embed to be displayed in the chat where the command was called.

    Args:
        user (discord.Member): The user who was actioned against
        action (str): The string representation of the action type
        reason (str): The reason the action was taken

    Returns:
        discord.Embed: The formatted embed ready to be sent
    """
    embed = discord.Embed(
        title="Chat Protection", description=f"{action.upper()} `{user}`"
    )
    embed.add_field(name="Reason", value=reason)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.color = discord.Color.gold()

    return embed


def build_warning_embeds(
    guild: discord.Guild,
    member: discord.Member,
    warnings: list[bot.models.UserNote],
) -> list[discord.Embed]:
    """Makes a list of embeds with 6 warnings per page, for a given user

    Args:
        guild (discord.Guild): The guild where the warnings occured
        member (discord.Member): The member whose warnings are being looked for
        warnings (list[bot.models.UserNote]): The list of warnings from the database

    Returns:
        list[discord.Embed]: The list of well formatted embeds
    """
    embed = auxiliary.generate_basic_embed(
        f"Warnings for `{member.display_name}` (`{member.name}`)",
        color=discord.Color.dark_blue(),
    )
    embed.set_footer(text=f"{len(warnings)} total warns.")

    embeds = []

    if not warnings:
        embed.description = "No warnings"
        return [embed]

    for index, warn in enumerate(warnings):
        if index % 6 == 0 and index > 0:
            embeds.append(embed)
            embed = auxiliary.generate_basic_embed(
                f"Warnings for `{member.display_name}` (`{member.name}`)",
                color=discord.Color.dark_blue(),
            )
            embed.set_footer(text=f"{len(warnings)} total warns.")
        warn_author = "Unknown"
        if warn.invoker_id:
            warn_author = warn.invoker_id
            author = guild.get_member(int(warn.invoker_id))
            if author:
                warn_author = author.name
        embed.add_field(
            name=f"Warned by {warn_author}",
            value=f"{warn.reason}\nWarned <t:{int(warn.time.timestamp())}:R>",
        )
    embeds.append(embed)
    return embeds
