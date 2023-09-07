"""Module for defining the application bot methods."""
import datetime
import io
import json
import uuid

import aiocron
import discord
import ui
import yaml
from base import auxiliary, cogs
from botlogging import LogContext, LogLevel
from discord import app_commands
from discord.ext import commands


async def setup(bot):
    """
    Method to setup the bot, and configure different management role config options for
    the promotion application framework.
    """
    # For the webhook id to add to discord
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
    async def execute(self, config, guild):
        channels = config.extensions.application.notification_channels.value
        for channel in channels:
            channel = guild.get_channel(int(channel))
            if not channel:
                continue

            await ui.AppNotice(timeout=None).send(
                channel=channel,
                message=config.extensions.application.application_message.value,
            )

    async def wait(self, config, _):
        await aiocron.crontab(
            config.extensions.application.notification_cron_config.value
        ).next()


class ApplicationManager(cogs.LoopCog):
    """Class to manage the application extension of the bot, including getting data and status."""

    @app_commands.command(
        name="apply",
        description="Use this to show you are interested in being staff on this server",
    )
    async def apply(self, interaction: discord.Interaction):
        # Send the modal with an instance of our `Feedback` class
        # Since modals require an interaction, they cannot be done as a response to a text command.
        # They can only be done as a response to either an application command or a button press.
        can_apply = await self.check_if_can_apply(interaction.user)
        if not can_apply:
            await interaction.response.send_message(
                "You are not eligible to apply right now. Ask the server moderators if"
                " you have questions",
                ephemeral=True,
            )
            return
        form = ui.Application()
        await interaction.response.send_modal(form)
        await form.wait()
        await self.handle_new_application(
            interaction.user, form.background.value, form.reason.value
        )

    def build_application_embed(
        self, applicant: discord.Member, background: str, reason: str
    ) -> discord.Embed:
        embed = discord.Embed()
        embed.timestamp = datetime.datetime.utcnow()
        embed.title = "New Application!"
        embed.color = discord.Color.green()
        embed.set_thumbnail(url=applicant.display_avatar.url)
        embed.add_field(
            name="Name",
            value=f"{applicant.display_name} ({applicant.name})",
            inline=False,
        )
        embed.add_field(
            name="Do you have any IT or programming experience?",
            value=background,
            inline=False,
        )
        embed.add_field(
            name="Why do you want to help here?",
            value=reason,
            inline=False,
        )

        return embed

    async def handle_new_application(
        self, applicant: discord.Member, background: str, reason: str
    ):
        # Find the channel to send to
        config = await self.bot.get_context_config(guild=applicant.guild)
        channel = applicant.guild.get_channel(
            int(config.extensions.application.management_channel.value)
        )

        embed = self.build_application_embed(applicant, background, reason)

        await channel.send(embed=embed)

    async def check_if_can_apply(self, applicant: discord.Member):
        config = await self.bot.get_context_config(guild=applicant.guild)
        role = applicant.guild.get_role(
            int(config.extensions.application.application_role.value)
        )
        # Don't allow people to apply if they already have the role
        if role in getattr(applicant, "roles", []):
            return False
        return True

    async def execute(self, config, guild):
        """Method to execute the news command."""
        channel = guild.get_channel(
            int(config.extensions.application.management_channel.value)
        )
        if not channel:
            return

        await channel.send("manager")

    async def wait(self, config, _):
        await aiocron.crontab(
            config.extensions.application.reminder_cron_config.value
        ).next()
