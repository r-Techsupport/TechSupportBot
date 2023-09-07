"""Module for defining the application extension"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import TYPE_CHECKING

import aiocron
import discord
import munch
import ui
from base import auxiliary, cogs
from botlogging import LogContext, LogLevel
from discord import app_commands

if TYPE_CHECKING:
    import bot


class ApplicationStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    REJECTED = "rejected"


async def setup(bot: bot.TechSupportBot) -> None:
    """The setup function to define config and add the cogs to the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    config = bot.ExtensionConfig()
    config.add(
        key="management_channel",
        datatype="int",
        title="ID of the staff side channel",
        description=(
            "The ID of the channel the application notifications and reminders should"
            " appear in"
        ),
        default=None,
    )
    config.add(
        key="notification_channels",
        datatype="list",
        title="List of channels to get application",
        description=(
            "The list of channel IDs that should receive periodic messages about the"
            " application, with a button to apply"
        ),
        default=None,
    )
    config.add(
        key="reminder_cron_config",
        datatype="string",
        title="Cronjob config for the reminder about pending applications for staff",
        description=(
            "Crontab syntax for executing pending reminder events (example: 0 17 * * *)"
        ),
        default="0 17 * * *",
    )
    config.add(
        key="notification_cron_config",
        datatype="string",
        title="Cronjob config for the user facting notification",
        description=(
            "Crontab syntax for users being notified about the application (example: 0"
            " */3 * * *)"
        ),
        default="0 */3 * * *",
    )
    config.add(
        key="application_message",
        datatype="str",
        title="Message on the application reminder",
        description=(
            "The message to show users when they are prompted to apply in the"
            " notification_channels"
        ),
        default="Apply now!",
    )
    config.add(
        key="application_role",
        datatype="str",
        title="ID of the role to give applicants",
        description=(
            "The ID of the role to give applicants when there application is approved"
        ),
        default=None,
    )
    await bot.add_cog(ApplicationManager(bot=bot, extension_name="application"))
    await bot.add_cog(ApplicationNotifier(bot=bot, extension_name="application"))
    bot.add_extension_config("application", config)


class ApplicationNotifier(cogs.LoopCog):
    """This cog is soley tasked with looping the application reminder for users
    Everything else is handled in ApplicationManager"""

    async def execute(self, config: munch.Munch, guild: discord.Guild) -> None:
        """The function that executes the from the LoopCog structure

        Args:
            config (munch.Munch): The guild config for the executing loop
            guild (discord.Guild): The guild the loop is executing for
        """
        channels = config.extensions.application.notification_channels.value
        for channel in channels:
            channel = guild.get_channel(int(channel))
            if not channel:
                continue

            await ui.AppNotice(timeout=None).send(
                channel=channel,
                message=config.extensions.application.application_message.value,
            )

    async def wait(self, config: munch.Munch, guild: discord.Guild) -> None:
        """The function that causes the sleep/delay the from the LoopCog structure

        Args:
            config (munch.Munch): The guild config for the executing loop
            guild (discord.Guild): The guild the loop is executing for
        """
        await aiocron.crontab(
            config.extensions.application.notification_cron_config.value
        ).next()


class ApplicationManager(cogs.LoopCog):
    """This cog is responsible for the majority of functions in the application system"""

    application_group = app_commands.Group(name="application", description="...")

    # Slash Commands

    @app_commands.command(
        name="apply",
        description="Use this to show you are interested in being staff on this server",
    )
    async def apply(self, interaction: discord.Interaction) -> None:
        """The slash command entrance for /apply
        This handles sending the form and checking if application is valid

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        await self.start_application(interaction)

    @application_group.command(
        name="ban", description="Ban someone from making new applications"
    )
    async def ban_user(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        is_banned = await self.check_if_banned(member)
        if is_banned:
            embed = auxiliary.prepare_deny_embed(
                f"{member.name} is already banned from making applications"
            )
            await interaction.response.send_message(embed=embed)
            return
        ban = self.bot.models.AppBans(
            guild_id=str(interaction.guild.id),
            applicant_id=str(member.id),
        )
        await ban.create()
        embed = auxiliary.prepare_confirm_embed(
            f"{member.name} successfully banned from making applications"
        )
        await interaction.response.send_message(embed=embed)

    @application_group.command(
        name="unban", description="Unban someone and allow them to apply"
    )
    async def unban_user(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        is_banned = await self.check_if_banned(member)
        if not is_banned:
            embed = auxiliary.prepare_deny_embed(
                f"{member.name} is not banned from making applications"
            )
            await interaction.response.send_message(embed=embed)
            return
        bans = await self.get_ban_entry(member)
        for ban in bans:
            await ban.delete()
        embed = auxiliary.prepare_confirm_embed(
            f"{member.name} successfully unbanned from making applications"
        )
        await interaction.response.send_message(embed=embed)

    @application_group.command(
        name="get", description="Gets the application of the given user"
    )
    async def get_application(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        allow_old: bool = False,
    ) -> None:
        if allow_old:
            await self.get_command_all(interaction, member)
        else:
            await self.get_command_pending(interaction, member)

    @application_group.command(
        name="approve", description="Approves an application of the given user"
    )
    async def approve_application(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        message: str = None,
    ) -> None:
        application = await self.search_for_pending_application(member)
        if not application:
            embed = auxiliary.prepare_deny_embed(
                f"No application could be found for {member.name}"
            )
            await interaction.response.send_message(embed=embed)
            return
        await application.update(
            application_stauts=ApplicationStatus.APPROVED.value
        ).apply()

        confirm_message = f"{member.name}'s application was successfully approved"

        if message:
            member = await self.get_application_from_db_entry(
                interaction.guild, application
            )
            embed = auxiliary.prepare_confirm_embed(
                f"Your application in {interaction.guild.name} has been approved!"
                f" Message from the staff: {message}"
            )
            try:
                await member.send(embed=embed)
                confirm_message += " and they have been notified"
            except discord.Forbidden as exception:
                confirm_message += (
                    f" but there was an error notifying them: {exception}"
                )

        else:
            confirm_message += " silently"

        embed = auxiliary.prepare_confirm_embed(confirm_message)

        await interaction.response.send_message(embed=embed)

    # Get application functions

    async def get_command_all(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        applications = await self.search_for_all_applications(member)
        if not applications:
            embed = auxiliary.prepare_deny_embed(
                f"No applications could be found for {member.name}"
            )
            await interaction.response.send_message(embed=embed)
            return
        await interaction.response.send_message(
            f"Gathering all applications for {member.name}. There might be a delay"
        )
        embeds = [
            await self.build_application_embed(
                guild=interaction.guild, application=application, new=False
            )
            for application in applications
        ]
        # Reverse it so the latest application is page 1
        embeds.reverse()
        await ui.PaginateView().send(interaction.channel, interaction.user, embeds)

    async def get_command_pending(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        application = await self.search_for_pending_application(member)
        if not application:
            embed = auxiliary.prepare_deny_embed(
                f"No application could be found for {member.name}"
            )
        else:
            embed = await self.build_application_embed(
                interaction.guild, application, False
            )
        await interaction.response.send_message(embed=embed)

    # Helper functions

    async def start_application(self, interaction: discord.Interaction) -> None:
        can_apply = await self.check_if_can_apply(interaction.user)
        if not can_apply:
            await interaction.response.send_message(
                "You are not eligible to apply right now. Ask the server moderators if"
                " you have questions.",
                ephemeral=True,
            )
            return
        form = ui.Application()
        await interaction.response.send_modal(form)
        await form.wait()
        await self.handle_new_application(
            interaction.user, form.background.value, form.reason.value
        )

    async def check_if_banned(self, member: discord.Member) -> bool:
        entry = await self.get_ban_entry(member)
        if entry:
            return True
        else:
            return False

    async def get_application_from_db_entry(
        self, guild: discord.Guild, application: bot.models.Applications
    ) -> discord.Member:
        applicant = guild.get_member(int(application.applicant_id))
        return applicant

    async def build_application_embed(
        self,
        guild: discord.Guild,
        application: bot.models.Applications,
        new: bool = True,
    ) -> discord.Embed:
        """This builds the embed that will be sent to staff

        Args:
            applicant (discord.Member): The member who has applied
            background (str): The answer to the background question
            reason (str): The answer to the reason question

        Returns:
            discord.Embed: The stylized embed ready to be show to people
        """
        if not application:
            return None
        applicant = await self.get_application_from_db_entry(guild, application)
        if not applicant:
            return None

        embed = discord.Embed()
        embed.timestamp = application.application_time
        if new:
            embed.title = "New Application!"
        else:
            embed.title = "Application"
        embed.color = discord.Color.green()
        embed.set_thumbnail(url=applicant.display_avatar.url)
        embed.add_field(
            name="Name",
            value=f"{applicant.display_name} ({application.applicant_name})",
            inline=False,
        )
        embed.add_field(
            name="Do you have any IT or programming experience?",
            value=application.background,
            inline=False,
        )
        embed.add_field(
            name="Why do you want to help here?",
            value=application.reason,
            inline=False,
        )
        embed.add_field(
            name="Status",
            value=application.application_stauts,
            inline=False,
        )

        return embed

    async def handle_new_application(
        self, applicant: discord.Member, background: str, reason: str
    ) -> None:
        """The function that handles what happens when a new application is sent in

        Args:
            applicant (discord.Member): The member who has applied
            background (str): The answer to the background question
            reason (str): The answer to the reason question
        """
        # Add application to database
        application = self.bot.models.Applications(
            guild_id=str(applicant.guild.id),
            applicant_name=applicant.name,
            applicant_id=str(applicant.id),
            application_stauts=ApplicationStatus.PENDING.value,
            background=background,
            reason=reason,
        )
        await application.create()

        # Find the channel to send to
        config = await self.bot.get_context_config(guild=applicant.guild)
        channel = applicant.guild.get_channel(
            int(config.extensions.application.management_channel.value)
        )

        # Send notice to staff channel
        embed = await self.build_application_embed(applicant.guild, application)
        await channel.send(embed=embed)

    async def check_if_can_apply(self, applicant: discord.Member) -> bool:
        """Checks if a user can apply to
        Currently does the following checks:
            - Does the user have the application role
            - Has the user been banned from making applications
            - Does the user currently have a pending application

        Args:
            applicant (discord.Member): The member who as applied

        Returns:
            bool: True if they can apply, False if they cannot apply
        """
        config = await self.bot.get_context_config(guild=applicant.guild)
        role = applicant.guild.get_role(
            int(config.extensions.application.application_role.value)
        )
        # Don't allow people to apply if they already have the role
        if role in getattr(applicant, "roles", []):
            return False

        # Don't allow banned users to apply
        if await self.check_if_banned(applicant):
            return False

        # Don't allow users with a pending application to apply
        if await self.search_for_pending_application(applicant):
            return False

        return True

    # DB Stuff

    async def search_for_all_applications(self, member: discord.Member):
        query = self.bot.models.Applications.query.where(
            self.bot.models.Applications.applicant_id == str(member.id)
        ).where(self.bot.models.Applications.guild_id == str(member.guild.id))
        entry = await query.gino.all()
        return entry

    async def search_for_pending_application(self, member: discord.Member):
        query = (
            self.bot.models.Applications.query.where(
                self.bot.models.Applications.applicant_id == str(member.id)
            )
            .where(self.bot.models.Applications.guild_id == str(member.guild.id))
            .where(
                self.bot.models.Applications.application_stauts
                == ApplicationStatus.PENDING.value
            )
        )
        entry = await query.gino.first()
        return entry

    async def get_ban_entry(self, member: discord.Member):
        query = self.bot.models.AppBans.query.where(
            self.bot.models.AppBans.applicant_id == str(member.id)
        ).where(self.bot.models.AppBans.guild_id == str(member.guild.id))
        entry = await query.gino.all()
        return entry

    # Loop stuff

    async def execute(self, config: munch.Munch, guild: discord.Guild) -> None:
        """The executes the reminder of pending applications

        Args:
            config (munch.Munch): The guild config for the executing loop
            guild (discord.Guild): The guild the loop is executing for
        """
        channel = guild.get_channel(
            int(config.extensions.application.management_channel.value)
        )
        if not channel:
            return

        await channel.send("manager")

    async def wait(self, config: munch.Munch, guild: discord.Guild) -> None:
        """The queues the pending application reminder based on the cron config

        Args:
            config (munch.Munch): The guild config for the executing loop
            guild (discord.Guild): The guild the loop is executing for
        """
        await aiocron.crontab(
            config.extensions.application.reminder_cron_config.value
        ).next()

    # Custom error handling

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction[discord.Client],
        error: app_commands.AppCommandError,
    ) -> None:
        """Error handler for the who extension."""
        message = ""
        if isinstance(error, app_commands.CommandNotFound):
            return

        if isinstance(error, app_commands.MissingPermissions):
            message = (
                "I am unable to do that because you lack the permission(s):"
                f" `{', '.join(error.missing_permissions)}`"
            )
            embed = auxiliary.prepare_deny_embed(message)

        else:
            embed = auxiliary.prepare_deny_embed(
                f"I ran into an error running that command {error}."
            )
            config = await self.bot.get_context_config(guild=interaction.guild)
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message=f"{error}",
                level=LogLevel.ERROR,
                channel=log_channel,
                context=LogContext(
                    guild=interaction.guild, channel=interaction.channel
                ),
                exception=error,
            )

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)
