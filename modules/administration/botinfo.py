"""
Commands which allow information about the bot to be shown
The cog in the file is named:
    BotInfo

This file contains 1 command:
    .bot
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

from core import auxiliary, cogs
from database import status as db_status

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the BotInfo plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(BotInfo(bot=bot))


class BotInfo(cogs.BaseCog):
    """
    The class that holds the bot command
    """

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @app_commands.command(
        name="bot",
        description="Provides bot info",
    )
    async def get_bot_data(self: Self, interaction: discord.Interaction) -> None:
        """Gets various data about the bot.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the interaction that called this command
        """
        embed = discord.Embed(title=self.bot.user.name, color=discord.Color.blurple())

        embed.add_field(
            name="Started",
            value=(
                f"<t:{int(self.bot.startup_time.timestamp())}:R>"
                if self.bot.startup_time
                else "Unknown"
            ),
            inline=True,
        )
        embed.add_field(
            name="Latency",
            value=f"{self.bot.latency * 1000} ms" if self.bot.latency else "None",
            inline=True,
        )
        embed.add_field(
            name="Description", value=self.bot.description or "None", inline=True
        )
        embed.add_field(
            name="Servers",
            value=", ".join(f"{guild.name} ({guild.id})" for guild in self.bot.guilds),
            inline=True,
        )

        connection_status = (
            await db_status.get_connection_status(self.bot.db)
        ).connected
        schema_status = (await db_status.get_schema_status(self.bot.db)).matches
        embed.add_field(
            name="Postgres",
            value=f"Status: `{"Connected" if connection_status else "Not connected"}`\n"
            + f"Schema matches: `{schema_status}`",
            inline=True,
        )

        irc_config = self.bot.file_config.api.irc
        if not irc_config.enable_irc:
            embed.add_field(
                name="IRC",
                value="IRC is not enabled",
                inline=True,
            )
        else:
            irc_status = self.bot.irc.get_irc_status()
            embed.add_field(
                name="IRC",
                value=f"IRC Status: `{irc_status['status']}`\n"
                + f"IRC Bot Name: `{irc_status['name']}`\n"
                + f"Channels: `{irc_status['channels']}`",
                inline=False,
            )

        version_info = "Not available"
        try:
            with open("resources/dynamic/version.json", "r", encoding="utf-8") as file:
                version = json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError):
            version = None

        if isinstance(version, dict):
            upstream: str = version.get("upstream")
            commit: str = version.get("commit")
            subject: str = version.get("subject")
            dirty: bool = version.get("dirty")
            if all(
                isinstance(value, str) and value
                for value in (upstream, commit, subject)
            ) and isinstance(dirty, bool):
                version_info = (
                    f"Upstream: `{upstream}`\n"
                    f"Commit: `{commit[:7]} - {subject}`\n"
                    f"Local changes made: `{dirty}`"
                )

        embed.add_field(name="Version Info", value=version_info, inline=False)

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)
