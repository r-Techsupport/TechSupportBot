"""The report command"""

from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs, extensionconfig
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
        key="alert_channel",
        datatype="int",
        title="Alert channel ID",
        description="The ID of the channel to send auto-protect alerts to",
        default=None,
    )
    await bot.add_cog(Report(bot=bot, extension_name="report"))
    bot.add_extension_config("report", config)


class Report(cogs.BaseCog):
    """The class that holds the report command and helper function"""

    @app_commands.command(
        name="report",
        description="Reports something to the moderators",
        extras={"module": "report"},
    )
    async def report_command(
        self: Self, interaction: discord.Interaction, report_str: str
    ) -> None:
        """This is the core of the /report command
        Allows users to report potential moderation issues to staff

        Args:
            interaction (discord.Interaction): The interaction that called this command
            report_str (str): The report string that the user submitted
        """
        if len(report_str) > 2000:
            embed = auxiliary.prepare_deny_embed(
                "Your report cannot be longer than 2000 characters."
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(title="New Report", description=report_str)
        embed.color = discord.Color.red()
        embed.set_author(
            name=interaction.user.name,
            icon_url=interaction.user.avatar.url or interaction.user.default_avatar.url,
        )

        embed.add_field(
            name="User info",
            value=(
                f"**Name:** {interaction.user.name} ({interaction.user.mention})\n"
                f"**Joined:** <t:{int(interaction.user.joined_at.timestamp())}:R>\n"
                f"**Created:** <t:{int(interaction.user.created_at.timestamp())}:R>\n"
                f"**Sent from:** {interaction.channel.mention} [Jump to context]"
                f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/"
                f"{discord.utils.time_snowflake(datetime.datetime.utcnow())})"
            ),
        )

        mention_pattern = re.compile(r"<@!?(\d+)>")
        mentioned_user_ids = mention_pattern.findall(report_str)

        mentioned_users = []
        for user_id in mentioned_user_ids:
            user = None
            try:
                user = await interaction.guild.fetch_member(int(user_id))
            except discord.NotFound:
                user = None
            if user:
                mentioned_users.append(user)
        mentioned_users: list[discord.Member] = set(mentioned_users)

        for index, user in enumerate(mentioned_users):
            embed.add_field(
                name=f"Mentioned user #{index+1}",
                value=(
                    f"**Name:** {user.name} ({user.mention})\n"
                    f"**Joined:** <t:{int(user.joined_at.timestamp())}:R>\n"
                    f"**Created:** <t:{int(user.created_at.timestamp())}:R>\n"
                    f"**ID:** {user.id}"
                ),
            )

        embed.set_footer(text=f"Author ID: {interaction.user.id}")
        embed.timestamp = datetime.datetime.utcnow()

        config = self.bot.guild_configs[str(interaction.guild.id)]

        try:
            alert_channel = interaction.guild.get_channel(
                int(config.extensions.report.alert_channel.value)
            )
        except TypeError:
            alert_channel = None

        if not alert_channel:
            user_embed = auxiliary.prepare_deny_embed(
                message="An error occurred while processing your report. It was not sent."
            )
            await interaction.response.send_message(embed=user_embed, ephemeral=True)
            return

        await alert_channel.send(embed=embed)

        user_embed = auxiliary.prepare_confirm_embed(
            message="Your report was successfully sent"
        )
        await interaction.response.send_message(embed=user_embed, ephemeral=True)
