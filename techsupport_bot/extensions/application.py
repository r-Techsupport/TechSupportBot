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
        description="The ID of the channel the application notifications and reminders should appear in",
        default=None,
    )
    config.add(
        key="reminder_cron_config",
        datatype="string",
        title="Cronjob config for the reminder about pending applications for staff",
        description="Crontab syntax for executing pending reminder events (example: 0 17 * * *)",
        default="* * * * *",
    )
    await bot.add_cog(ApplicationManager(bot=bot, extension_name="application"))
    bot.add_extension_config("application", config)


class ApplicationManager(base.LoopCog):
    """Class to manage the application extension of the bot, including getting data and status."""

    COLLECTION_NAME = "applications_extension"
    STALE_APPLICATION_DAYS = 30
    MAX_REMINDER_FIELDS = 10
    CHANNELS_KEY = "management_channel"

    @app_commands.command(name="feedback", description="Submit feedback")
    async def feedback(self, interaction: discord.Interaction):
        # Send the modal with an instance of our `Feedback` class
        # Since modals require an interaction, they cannot be done as a response to a text command.
        # They can only be done as a response to either an application command or a button press.
        await interaction.response.send_modal(ui.Feedback())

    async def execute(self, config, guild):
        """Method to execute the news command."""
        channel = guild.get_channel(int(config.extensions.news.channel.value))
        if not channel:
            return

        await channel.send("test 2")

    async def wait(self, config, _):
        """Method to define the wait time for the news api pull."""
        await aiocron.crontab(
            config.extensions.application.reminder_cron_config.value
        ).next()
