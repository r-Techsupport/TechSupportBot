"""
Commands which allow admins to echo messages from the bot
The cog in the file is named:
    MessageEcho

This file contains 2 commands:
    /echo user
    /echo channel
"""

from __future__ import annotations

import discord.abc
from discord import app_commands
from discord.ext import commands

from typing import TYPE_CHECKING, Self

from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Echo plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(MessageEcho(bot=bot, extension_name="echo"))


class MessageEcho(cogs.BaseCog):
    """
    The class that holds the echo commands
    """

    echo: app_commands.Group = app_commands.Group(
        name="echo", description="...", extras={"module": "echo"}
    )

    @commands.check(auxiliary.bot_admin_check_context)
    @echo.command(
        name="channel",
        description="Echos a message to a channel",
        extras={"module": "echo"},
    )
    async def echo_channel(
        self: Self,
        interaction: discord.Interaction,
        channel: discord.Thread | discord.TextChannel | discord.VoiceChannel,
        *,
        message: str,
    ) -> None:
        """Sends a message to a specified channel.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the associated interaction
            channel (discord.Thread|discord.TextChannel|discord.VoiceChannel): channel to send the message to
            message (str): the message to echo
        """
        try:
            await channel.send(content=message)
        except discord.Forbidden:
            embed = auxiliary.prepare_deny_embed(message="Unable to send message")
            await interaction.response.send_message(embed=embed)
            return

        embed = auxiliary.prepare_confirm_embed(message="Message sent!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.check(auxiliary.bot_admin_check_context)
    @echo.command(
        name="user",
        description="Echos a message to a user",
        extras={"module": "echo"},
    )
    async def echo_user(
        self: Self, interaction: discord.Interaction, user: discord.User, message: str
    ) -> None:
        """Sends a message to a specified user.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the associated interaction
            user (discord.User): the the user to send the echoed message
            message (str): the message to echo
        """

        if user.bot:
            embed = auxiliary.prepare_deny_embed(message="You cannot message a bot")
            await interaction.response.send_message(embed=embed)
            return

        try:
            await user.send(content=message)
        except discord.Forbidden:
            embed = auxiliary.prepare_deny_embed(
                message="Unable to send message to this user"
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = auxiliary.prepare_confirm_embed(message="Message sent!")
        await interaction.response.send_message(embed=embed, ephemeral=True)
