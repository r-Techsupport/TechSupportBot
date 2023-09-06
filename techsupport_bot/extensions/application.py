"""Module for defining the application bot methods."""
import datetime
import io
import json
import uuid

import aiocron
import base
import discord
import ui
import yaml
from base import auxiliary
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
            " 17 * * *)"
        ),
        default="0 */3 * * *",
    )
    await bot.add_cog(ApplicationManager(bot=bot, extension_name="application"))
    await bot.add_cog(ApplicationNotifier(bot=bot, extension_name="application"))
    bot.add_extension_config("application", config)


class ApplicationNotifier(base.LoopCog):
    async def execute(self, config, guild):
        channels = config.extensions.application.notification_channels.value
        for channel in channels:
            channel = guild.get_channel(int(channel))
            if not channel:
                continue

            await channel.send("reminder")

    async def wait(self, config, _):
        await aiocron.crontab(
            config.extensions.application.notification_cron_config.value
        ).next()


class ApplicationManager(base.LoopCog):
    """Class to manage the application extension of the bot, including getting data and status."""

    @app_commands.command(name="feedback", description="Submit feedback")
    async def feedback(self, interaction: discord.Interaction):
        # Send the modal with an instance of our `Feedback` class
        # Since modals require an interaction, they cannot be done as a response to a text command.
        # They can only be done as a response to either an application command or a button press.
        form = ui.Feedback()
        await interaction.response.send_modal(form)
        await form.wait()
        await self.handle_new_application(
            interaction.user, form.background.value, form.reason.value
        )

    async def handle_new_application(
        self, applicant: discord.Member, background: str, reason: str
    ):
        print("NEW APPLICATION")
        config = await self.bot.get_context_config(guild=applicant.guild)
        channel = applicant.guild.get_channel(
            int(config.extensions.application.management_channel.value)
        )
        await channel.send(
            f"USER: {applicant}, background: {background}, reason: {reason}"
        )

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
