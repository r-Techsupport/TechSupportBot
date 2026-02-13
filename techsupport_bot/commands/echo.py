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

import discord
from core import auxiliary, cogs
from discord import app_commands
from functions import logger as function_logger

if TYPE_CHECKING:
    import bot
    import munch


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
        echo_group (app_commands.Group): The group for the /echo commands
    """

    echo_group: app_commands.Group = app_commands.Group(
        name="echo",
        description="Command Group for Echo Commands",
        extras={"module": "echo"},
    )

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @echo_group.command(
        name="channel",
        description="Echos a message to a channel",
        extras={
            "brief": "Echos a message to a channel",
            "usage": "#channel [message]",
            "module": "echo",
        },
    )
    async def echo_channel(
        self: Self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
    ) -> None:
        """Sends a message to a specified channel.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            channel (discord.TextChannel): The channel to send the echoed message to
            message (str): the message to echo
        """
        await interaction.response.defer(ephemeral=True)
        sent_message = await channel.send(content=message)
        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed("Message sent"), ephemeral=True
        )

        config = self.bot.guild_configs[str(channel.guild.id)]
        logging_payload = build_echo_channel_log_payload(config, message)
        if not logging_payload:
            return

        target_logging_channel = await function_logger.pre_log_checks(
            self.bot, config, channel
        )
        if not target_logging_channel:
            return

        await function_logger.send_message(
            self.bot,
            sent_message,
            interaction.user,
            channel,
            target_logging_channel,
            content_override=logging_payload["content_override"],
            special_flags=logging_payload["special_flags"],
        )

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @echo_group.command(
        name="user",
        description="Echos a message to a user",
        extras={
            "brief": "Echos a message to a user",
            "usage": "@user [message]",
            "module": "echo",
        },
    )
    async def echo_user(
        self: Self, interaction: discord.Interaction, user: discord.User, message: str
    ) -> None:
        """Sends a message to a specified user.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.User): The user to send the echoed message to
            message (str): the message to echo
        """
        await interaction.response.defer(ephemeral=True)
        await user.send(content=message)
        await interaction.followup.send(
            embed=auxiliary.prepare_confirm_embed("Message sent"), ephemeral=True
        )


def normalize_echo_message(message: str) -> str:
    """Normalizes user supplied message text for consistent logging payloads.

    Args:
        message (str): The message provided to the echo command

    Returns:
        str: A non-empty message string suitable for log output
    """
    normalized_message = message.strip()
    if len(normalized_message) == 0:
        return "No content"
    return normalized_message


def build_echo_channel_log_payload(
    config: munch.Munch, message: str
) -> dict[str, str | list[str]] | None:
    """Builds the payload needed by the logger extension for /echo channel.

    Args:
        config (munch.Munch): The guild config for the channel where the echo happened
        message (str): The message that was echoed

    Returns:
        dict[str, str | list[str]] | None: A prepared payload for logger calls.
            Returns None when the logger extension is disabled.
    """
    enabled_extensions = set(config.enabled_extensions)
    if "logger" not in enabled_extensions:
        return None

    return {
        "content_override": normalize_echo_message(message),
        "special_flags": ["Echo command"],
    }
