"""Module for defining the application extension"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Self

import aiocron
import discord
import munch
import ui
from core import auxiliary, cogs, extensionconfig
from discord import app_commands

if TYPE_CHECKING:
    import bot


class ApplicationStatus(Enum):
    """Static string mapping of all status
    This is so the database can always be consistent

    Attrs:
        PENDING (str): The string representation for pending
        APPROVED (str): The string representation for approved
        DENIED (str): The string representation for denied
        REJECTED (str): The string representation for rejected
    """

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    REJECTED = "rejected"


async def setup(bot: bot.TechSupportBot) -> None:
    """The setup function to define config and add the cogs to the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="management_channel",
        datatype="str",
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
        title="Cronjob config for the user facing notification",
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
    config.add(
        key="manage_roles",
        datatype="list",
        title="Manage application roles",
        description=(
            "The role IDs required to manage the applications (not required to apply)"
        ),
        default=[""],
    )
    config.add(
        key="ping_role",
        datatype="str",
        title="New application ping role",
        description="The ID of the role to ping when a new application is created",
        default="",
    )
    await bot.add_cog(ApplicationManager(bot=bot, extension_name="application"))
    await bot.add_cog(ApplicationNotifier(bot=bot, extension_name="application"))
    bot.add_extension_config("application", config)


async def command_permission_check(interaction: discord.Interaction) -> bool:
    """This does permission checks and logs slash commands in this module
    This checks the interaction user against the manage roles config option

    Args:
        interaction (discord.Interaction): The interaction that was generated from the slash command

    Raises:
        AppCommandError: If there are no roles configured
        MissingAnyRole: If the executing user is missing the required roles

    Returns:
        bool: Will return true if the command is allowed to execute, false if it should not execute
    """
    # Get the bot object for easier access
    bot = interaction.client

    # Get the config
    config = bot.guild_configs[str(interaction.guild.id)]

    # Gets permitted roles
    allowed_roles = []
    for role_id in config.extensions.application.manage_roles.value:
        role = interaction.guild.get_role(int(role_id))
        if not role:
            continue
        allowed_roles.append(role)

    if not allowed_roles:
        raise app_commands.AppCommandError(
            "No application management roles found in the config file"
        )

    # Checking against the user to see if they have the roles specified in the config
    if not any(
        role in getattr(interaction.user, "roles", []) for role in allowed_roles
    ):
        raise app_commands.MissingAnyRole(allowed_roles)

    return True


class ApplicationNotifier(cogs.LoopCog):
    """This cog is soley tasked with looping the application reminder for users
    Everything else is handled in ApplicationManager"""

    async def execute(self: Self, config: munch.Munch, guild: discord.Guild) -> None:
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

    async def wait(self: Self, config: munch.Munch, guild: discord.Guild) -> None:
        """The function that causes the sleep/delay the from the LoopCog structure

        Args:
            config (munch.Munch): The guild config for the executing loop
            guild (discord.Guild): The guild the loop is executing for
        """
        await aiocron.crontab(
            config.extensions.application.notification_cron_config.value
        ).next()


class ApplicationManager(cogs.LoopCog):
    """This cog is responsible for the majority of functions in the application system

    Attrs:
        application_group (app_commands.Group): The group for the /application commands
    """

    application_group = app_commands.Group(
        name="application", description="...", extras={"module": "application"}
    )

    # Slash Commands

    @app_commands.command(
        name="apply",
        description="Use this to show you are interested in being staff on this server",
        extras={"module": "application"},
    )
    async def apply(self: Self, interaction: discord.Interaction) -> None:
        """The slash command entrance for /apply
        This handles sending the form and checking if application is valid

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        await self.start_application(interaction)

    @app_commands.check(command_permission_check)
    @application_group.command(
        name="ban",
        description="Ban someone from making new applications",
        extras={"module": "application"},
    )
    async def ban_user(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Bans a user from making any further applications

        Args:
            interaction (discord.Interaction): The interaction generated by this slash command
            member (discord.Member): The member to ban from making applications
        """
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

    @app_commands.check(command_permission_check)
    @application_group.command(
        name="unban",
        description="Unban someone and allow them to apply",
        extras={"module": "application"},
    )
    async def unban_user(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Unbans a user from making applications

        Args:
            interaction (discord.Interaction): The interaction generated by this slash command
            member (discord.Member): The member to unban from making applications
        """
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

    @app_commands.check(command_permission_check)
    @application_group.command(
        name="get",
        description="Gets the application of the given user",
        extras={"module": "application"},
    )
    async def get_application(
        self: Self,
        interaction: discord.Interaction,
        member: discord.Member,
        allow_old: bool = False,
    ) -> None:
        """Gets either the latest pending application, or all applications from the given user

        Args:
            interaction (discord.Interaction): The interaction generated by this slash command
            member (discord.Member): The member to get applications from
            allow_old (bool, optional): If this is passed, it will get all applications
                from the user. Defaults to False.
        """
        if allow_old:
            await self.get_command_all(interaction, member)
        else:
            await self.get_command_pending(interaction, member)

    @app_commands.check(command_permission_check)
    @application_group.command(
        name="approve",
        description="Approves the application of the given user",
        extras={"module": "application"},
    )
    async def approve_application(
        self: Self,
        interaction: discord.Interaction,
        member: discord.Member,
        message: str = None,
    ) -> None:
        """Approves a pending application of the given user

        Args:
            interaction (discord.Interaction): The interaction generated by this slash command
            member (discord.Member): The member whose application should be approved
            message (str, optional): The message to send to the user.
                If none is passed, the application is approved silently. Defaults to None.
        """
        application = await self.search_for_pending_application(member)
        if not application:
            embed = auxiliary.prepare_deny_embed(
                f"No application could be found for {member.name}"
            )
            await interaction.response.send_message(embed=embed)
            return

        application_role = await self.get_application_role(interaction.guild)
        if not application_role:
            embed = auxiliary.prepare_deny_embed(
                "This application could not be approved because no role to assign has"
                " been set in the config"
            )
            await interaction.response.send_message(embed=embed)
            return

        await application.update(
            application_status=ApplicationStatus.APPROVED.value
        ).apply()

        await member.add_roles(
            application_role, reason=f"Application approved by {interaction.user}"
        )

        await self.notify_for_application_change(
            message, True, interaction, application, member
        )

    @app_commands.check(command_permission_check)
    @application_group.command(
        name="deny",
        description="Denies the application of the given user",
        extras={"module": "application"},
    )
    async def deny_application(
        self: Self,
        interaction: discord.Interaction,
        member: discord.Member,
        message: str = None,
    ) -> None:
        """Denies a pending application of the given user

        Args:
            interaction (discord.Interaction): The interaction generated by this slash command
            member (discord.Member): The member whose application should be denied
            message (str, optional): The message to send to the user.
                If none is passed, the application is denied silently. Defaults to None.
        """
        application = await self.search_for_pending_application(member)
        if not application:
            embed = auxiliary.prepare_deny_embed(
                f"No application could be found for {member.name}"
            )
            await interaction.response.send_message(embed=embed)
            return
        await application.update(
            application_status=ApplicationStatus.DENIED.value
        ).apply()

        await self.notify_for_application_change(
            message, False, interaction, application, member
        )

    @app_commands.check(command_permission_check)
    @app_commands.checks.has_permissions(administrator=True)
    @application_group.command(
        name="delete",
        description="Deletes all applications from a user",
        extras={"module": "application"},
    )
    async def delete_applications(
        self: Self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        """Deletes all applications of a given user, regardless of state

        Args:
            interaction (discord.Interaction): The interaction generated by this slash command
            member (discord.Member): The member to delete all applications from
        """
        applications = await self.search_for_all_applications(member)
        if not applications:
            embed = auxiliary.prepare_deny_embed(
                f"No applications could be found for {member.name}"
            )
            await interaction.response.send_message(embed=embed)
            return
        for application in applications:
            await application.delete()
        embed = auxiliary.prepare_confirm_embed(
            f"Applications from {member.name} have been successfully deleted"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.check(command_permission_check)
    @application_group.command(
        name="list",
        description="Lists all applications by a given status",
        extras={"module": "application"},
    )
    async def list_applications(
        self: Self,
        interaction: discord.Interaction,
        status: ApplicationStatus,
    ) -> None:
        """Returns a paginated list of all applications from a given status

        Args:
            interaction (discord.Interaction): The interaction genereted by this slash command
            status (ApplicationStatus): The specified status to get applications from
        """
        applications = await self.get_applications_by_status(status, interaction.guild)
        if len(applications) == 0:
            embed = auxiliary.prepare_deny_embed(
                "No applications with that status exist"
            )
            await interaction.response.send_message(embed=embed)
            return
        await interaction.response.defer(ephemeral=False)
        embeds = await self.make_array_from_applications(
            applications, interaction.guild
        )
        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)

    # Get application functions

    async def get_command_all(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Gets all applications for a user, regardless of state, and sends them
        As a followup using PaginateView

        Args:
            interaction (discord.Interaction): The interaction generated by this slash command
            member (discord.Member): The member to get all applications of
        """
        applications = await self.search_for_all_applications(member)
        if not applications:
            embed = auxiliary.prepare_deny_embed(
                f"No applications could be found for {member.name}"
            )
            await interaction.response.send_message(embed=embed)
            return
        await interaction.response.defer(ephemeral=False)
        embeds = await self.make_array_from_applications(
            applications, interaction.guild
        )
        view = ui.PaginateView()
        await view.send(interaction.channel, interaction.user, embeds, interaction)

    async def get_command_pending(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Gets the most recent pending application of the given user

        Args:
            interaction (discord.Interaction): The interaction generated by this slash command
            member (discord.Member): The member to get the application from
        """
        application = await self.search_for_pending_application(member)
        if not application:
            embed = auxiliary.prepare_deny_embed(
                f"No pending application could be found for {member.name}"
            )
        else:
            embed = await self.build_application_embed(
                interaction.guild, application, False
            )
        await interaction.response.send_message(embed=embed)

    # Helper functions

    async def make_array_from_applications(
        self: Self, applications: bot.models.Applications, guild: discord.Guild
    ) -> list[discord.Embed]:
        """Makes an array designed for pagination from a list of applications

        Args:
            applications (bot.models.Applications): The list of applications to convert into embeds
            guild (discord.Guild): The guild the command is run from

        Returns:
            list[discord.Embed]: The list of embeds, with the newest application being element 0
        """
        embeds = [
            await self.build_application_embed(
                guild=guild, application=application, new=False
            )
            for application in applications
        ]
        # Reverse it so the latest application is page 1
        embeds.reverse()
        return embeds

    async def start_application(self: Self, interaction: discord.Interaction) -> None:
        """Starts the application process and sends the user the modal

        Args:
            interaction (discord.Interaction): The interaction that requested the application.
                Can be a button press or slash command
        """
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
        can_apply = await self.check_if_can_apply(interaction.user)
        if not can_apply:
            await interaction.followup.send(
                "Something went wrong when submitting your application. Try again or"
                " message the server moderators.",
                ephemeral=True,
            )
            return
        await self.handle_new_application(
            interaction.user, form.background.value, form.reason.value
        )

        await interaction.followup.send(
            f"Your application has been recieved, {interaction.user.display_name}!",
            ephemeral=True,
        )

        try:
            embed = auxiliary.prepare_confirm_embed(
                f"Your application in {interaction.guild.name} was successfully"
                " received!"
            )
            await interaction.user.send(embed=embed)
        except discord.Forbidden:
            pass

    async def check_if_banned(self: Self, member: discord.Member) -> bool:
        """Checks if a given user is banned from making applications

        Args:
            member (discord.Member): The member to check if is banned

        Returns:
            bool: True if the are banned, false if they aren't
        """
        entry = await self.get_ban_entry(member)
        return bool(entry)

    async def get_application_from_db_entry(
        self: Self, guild: discord.Guild, application: bot.models.Applications
    ) -> discord.Member:
        """Gets the applicant member object from a db entry

        Args:
            guild (discord.Guild): The guild to search in
            application (bot.models.Applications): The application database entry
                to get the member from

        Returns:
            discord.Member: The member object that is associated with the application
        """
        applicant = await guild.fetch_member(int(application.applicant_id))
        return applicant

    async def build_application_embed(
        self: Self,
        guild: discord.Guild,
        application: bot.models.Applications,
        new: bool = True,
    ) -> discord.Embed:
        """This builds the embed that will be sent to staff

        Args:
            guild (discord.Guild): The guild the user has applied to
            application (bot.models.Applications): The database entry of the application
            new (bool, optional): If the application is new and the title should
                include new. Defaults to True.

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
        if not new:
            embed.add_field(
                name="Status",
                value=application.application_status,
                inline=False,
            )
        embed.set_footer(text=f"User ID: {applicant.id}")

        return embed

    async def handle_new_application(
        self: Self, applicant: discord.Member, background: str, reason: str
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
            application_status=ApplicationStatus.PENDING.value,
            background=background,
            reason=reason,
        )
        await application.create()

        # Find the channel to send to
        config = self.bot.guild_configs[str(applicant.guild.id)]
        channel = applicant.guild.get_channel(
            int(config.extensions.application.management_channel.value)
        )

        # Send notice to staff channel
        role = applicant.guild.get_role(
            int(config.extensions.application.ping_role.value)
        )
        content_string = ""
        if role:
            content_string = role.mention
        embed = await self.build_application_embed(applicant.guild, application)
        await channel.send(
            content=content_string,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    async def check_if_can_apply(self: Self, applicant: discord.Member) -> bool:
        """Checks if a user can apply to
        Currently does the following checks:
            - Does the user have the application role
            - Has the user been banned from making applications
            - Does the user currently have a pending application
            - Does the user have the ability to manage applications

        Args:
            applicant (discord.Member): The member who as applied

        Returns:
            bool: True if they can apply, False if they cannot apply
        """
        config = self.bot.guild_configs[str(applicant.guild.id)]
        role = applicant.guild.get_role(
            int(config.extensions.application.application_role.value)
        )
        # Don't allow applications if extension is disabled
        if "application" not in config.enabled_extensions:
            return False

        # Don't allow people to apply if they already have the role
        if role in getattr(applicant, "roles", []):
            return False

        # Don't allow banned users to apply
        if await self.check_if_banned(applicant):
            return False

        # Don't allow users who can manage the applications to apply
        allowed_roles = []
        for role_id in config.extensions.application.manage_roles.value:
            role = applicant.guild.get_role(int(role_id))
            if not role:
                continue
            allowed_roles.append(role)
        if any(role in getattr(applicant, "roles", []) for role in allowed_roles):
            return False

        # Don't allow users with a pending application to apply
        if await self.search_for_pending_application(applicant):
            return False

        return True

    async def get_application_role(
        self: Self, guild: discord.Guild
    ) -> discord.Role | None:
        """Gets the guild application role object from the config

        Args:
            guild (discord.Guild): The guild to search in

        Returns:
            discord.Role | None: Will return the role object from the guild,
                or none if the role could not be found
        """
        config = self.bot.guild_configs[str(guild.id)]
        role = guild.get_role(int(config.extensions.application.application_role.value))
        return role

    async def notify_for_application_change(
        self: Self,
        message: str,
        approved: bool,
        interaction: discord.Interaction,
        application: bot.models.Applications,
        member: discord.Member,
    ) -> None:
        """Notifies:
            - The invoker
            - The user
            - The management channel
        For every manual application change

        Args:
            message (str): The message provided by the staff.
                If this is None, no DM will be sent to the user
            approved (bool): Whether this application has been approved. If False, it is denied
            interaction (discord.Interaction): The interaction from the slash command
                that changed the status
            application (bot.models.Applications): The db entry of the application to update
            member (discord.Member): The member to approve/deny,
                only for the purposes of sending a DM
        """
        string_status = "approved" if approved else "denied"
        confirm_message = (
            f"{member.name}'s application was successfully {string_status}"
        )
        if message:
            member = await self.get_application_from_db_entry(
                interaction.guild, application
            )
            user_message = (
                f"Your application in {interaction.guild.name} has been"
                f" {string_status}! Message from the staff: {message}"
            )
            if approved:
                embed = auxiliary.prepare_confirm_embed(user_message)
            else:
                embed = auxiliary.prepare_deny_embed(user_message)
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

    # DB Stuff

    async def search_for_all_applications(
        self: Self, member: discord.Member
    ) -> list[bot.models.Applications]:
        """Gets ALL applications for a given user, regardless of status

        Args:
            member (discord.Member): The member to lookup applications for

        Returns:
            list[bot.models.Applications]: A list of all of the applications beloning to the user
        """
        query = self.bot.models.Applications.query.where(
            self.bot.models.Applications.applicant_id == str(member.id)
        ).where(self.bot.models.Applications.guild_id == str(member.guild.id))
        entry = await query.gino.all()
        return entry

    async def get_applications_by_status(
        self: Self, status: ApplicationStatus, guild: discord.Guild
    ) -> list[bot.models.Applications]:
        """Gets all applications of a given status

        Args:
            status (ApplicationStatus): The status to search for
            guild (discord.Guild): The guild to get applications from

        Returns:
            list[bot.models.Applications]: The list of applications in a oldest first order
        """
        query = self.bot.models.Applications.query.where(
            self.bot.models.Applications.application_status == status.value
        ).where(self.bot.models.Applications.guild_id == str(guild.id))
        entry = await query.gino.all()
        entry.sort(key=lambda entry: entry.application_time)
        return entry

    async def search_for_pending_application(
        self: Self, member: discord.Member
    ) -> bot.models.Applications:
        """Finds a pending application from the given user

        Args:
            member (discord.Member): The member to lookup the application for

        Returns:
            bot.models.Applications: The pending application object of the given user
        """
        query = (
            self.bot.models.Applications.query.where(
                self.bot.models.Applications.applicant_id == str(member.id)
            )
            .where(self.bot.models.Applications.guild_id == str(member.guild.id))
            .where(
                self.bot.models.Applications.application_status
                == ApplicationStatus.PENDING.value
            )
        )
        entry = await query.gino.first()
        return entry

    async def get_ban_entry(self: Self, member: discord.Member) -> bot.models.AppBans:
        """Gets the DB entry of a banned user

        Args:
            member (discord.Member): The member to tlookup the ban for

        Returns:
            bot.models.AppBans: The DB entry of the ban, if one was found
        """
        query = self.bot.models.AppBans.query.where(
            self.bot.models.AppBans.applicant_id == str(member.id)
        ).where(self.bot.models.AppBans.guild_id == str(member.guild.id))
        entry = await query.gino.all()
        return entry

    # Loop stuff

    async def execute(self: Self, config: munch.Munch, guild: discord.Guild) -> None:
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

        apps = await self.get_applications_by_status(ApplicationStatus.PENDING, guild)
        if not apps:
            return

        # Update the database
        audit_log = []
        for app in apps:
            try:
                user = await guild.fetch_member(int(app.applicant_id))
            except discord.NotFound:
                user = None
            if not user:
                audit_log.append(
                    f"Application by user: `{app.applicant_name}` was rejected because"
                    " they left"
                )
                await app.update(
                    application_status=ApplicationStatus.REJECTED.value
                ).apply()
                continue

            if user.name != app.applicant_name:
                audit_log.append(
                    f"Application by user: `{app.applicant_name}` had the stored name"
                    f" updated to `{user.name}`"
                )
                await app.update(applicant_name=user.name).apply()

            role = guild.get_role(
                int(config.extensions.application.application_role.value)
            )

            if role in getattr(user, "roles", []):
                audit_log.append(
                    f"Application by user: `{user.name}` was approved since they have"
                    f" the `{role.name}` role"
                )
                await app.update(
                    application_status=ApplicationStatus.APPROVED.value
                ).apply()
        if audit_log:
            embed = discord.Embed(title="Application manage events")
            for event in audit_log:
                if embed.description:
                    embed.description = f"{embed.description}\n{event}"
                else:
                    embed.description = f"{event}"
            await channel.send(embed=embed)

        apps = await self.get_applications_by_status(ApplicationStatus.PENDING, guild)
        if not apps:
            return

        embed = discord.Embed(title="All pending applcations")
        list_of_applicants = []

        for app in apps:
            member = await guild.fetch_member(int(app.applicant_id))
            list_of_applicants.append(
                (
                    f"Application by: `{member.display_name} ({app.applicant_name})`"
                    f", applied on: {app.application_time}"
                )
            )

        embed.description = "\n".join(list_of_applicants)

        await channel.send(embed=embed)

    async def wait(self: Self, config: munch.Munch, guild: discord.Guild) -> None:
        """The queues the pending application reminder based on the cron config

        Args:
            config (munch.Munch): The guild config for the executing loop
            guild (discord.Guild): The guild the loop is executing for
        """
        await aiocron.crontab(
            config.extensions.application.reminder_cron_config.value
        ).next()
