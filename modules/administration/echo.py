"""
Commands which allow admins to echo messages from the bot
The cog in the file is named:
    MessageEcho

This file contains 2 commands:
    /echo user
    /echo channel
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord.abc
from discord import app_commands

import configuration
from core import auxiliary, cogs
from modules.moderation import logger as function_logger

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Echo plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(MessageEcho(bot=bot))


class MessageEcho(cogs.BaseCog):
    """
    The class that holds the echo commands

    Attributes:
        echo_commands (app_commands.Group): The group for the /echo commands
    """

    echo_commands: app_commands.Group = app_commands.Group(
        name="echo",
        description="...",
    )

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @echo_commands.command(
        name="channel",
        description="Echos a message to a channel",
    )
    async def echo_channel(
        self: Self,
        interaction: discord.Interaction,
        channel: discord.Thread | discord.TextChannel | discord.VoiceChannel,
        message: str,
    ) -> None:
        """Sends a message to a specified channel.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the context object for the calling message
            channel (discord.Thread|discord.TextChannel|discord.VoiceChannel): the channel to send
                the message in
            message (str): the message to echo
        """

        sent_message = await channel.send(content=message)

        embed = auxiliary.prepare_confirm_embed("Message sent")
        await interaction.response.send_message(embed=embed)
        # Don't allow logging if extension is disabled
        if "moderation.logger" not in configuration.get_config_entry(
            channel.guild.id, "core_enabled_extensions"
        ):
            return

        target_logging_channel = await function_logger.pre_log_checks(self.bot, channel)
        if not target_logging_channel:
            return

        await function_logger.send_message(
            self.bot,
            sent_message,
            interaction.user,
            channel,
            target_logging_channel,
            content_override=message,
            special_flags=["Echo command"],
        )

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @echo_commands.command(
        name="user",
        description="Echos a message to a user",
    )
    async def echo_user(
        self: Self, interaction: discord.Interaction, user: discord.User, message: str
    ) -> None:
        """Sends a message to a specified user.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the context object for the calling message
            user (discord.User): who the message should be sent to
            message (str): the message to echo
        """

        await user.send(content=message)

        embed = auxiliary.prepare_confirm_embed("Message sent")
        await interaction.response.send_message(embed=embed)
