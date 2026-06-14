"""The report command"""

from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import configuration
from core import auxiliary, cogs
from modules.moderation import modlog

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(Report(bot=bot))


class Report(cogs.BaseCog):
    """The class that holds the report command and helper function"""

    @app_commands.command(
        name="report",
        description="Reports something to the moderators",
        extras={"suppress_logs": True},
    )
    async def report_command(
        self: Self, interaction: discord.Interaction, reason: str
    ) -> None:
        """This is the core of the /report command
        Allows users to report potential moderation issues to staff

        Args:
            interaction (discord.Interaction): The interaction that called this command
            reason (str): The report string that the user submitted
        """
        if len(reason) > 2000:
            embed = auxiliary.prepare_deny_embed(
                "Your report cannot be longer than 2000 characters."
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(title="New Report", description=reason)
        embed.color = discord.Color.red()

        is_anonymous = configuration.get_config_entry(
            interaction.guild.id, "report_anonymous"
        )

        if is_anonymous:
            embed.set_author(name="Anonymous")
        else:
            embed.set_author(
                name=interaction.user.name,
                icon_url=interaction.user.avatar.url
                or interaction.user.default_avatar.url,
            )
            embed.add_field(
                name="User info",
                value=(
                    f"**Name:** {interaction.user.name} ({interaction.user.mention})\n"
                    f"**Joined:** <t:{int(interaction.user.joined_at.timestamp())}:R>\n"
                    f"**Created:** <t:{int(interaction.user.created_at.timestamp())}:R>\n"
                ),
            )

        embed.add_field(
            name="** **",
            value=(
                f"**Sent from:** {interaction.channel.mention} [Jump to context]"
                f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/"
                f"{discord.utils.time_snowflake(datetime.datetime.utcnow())})"
            ),
        )

        mention_pattern = re.compile(r"<@!?(\d+)>")
        mentioned_user_ids = mention_pattern.findall(reason)

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
                name=f"Mentioned user #{index + 1}",
                value=(
                    f"**Name:** {user.name} ({user.mention})\n"
                    f"**Joined:** <t:{int(user.joined_at.timestamp())}:R>\n"
                    f"**Created:** <t:{int(user.created_at.timestamp())}:R>\n"
                    f"**ID:** {user.id}"
                ),
            )

        if not is_anonymous:
            embed.set_footer(text=f"Author ID: {interaction.user.id}")
        embed.timestamp = datetime.datetime.utcnow()

        try:
            alert_channel = interaction.guild.get_channel(
                int(
                    configuration.get_config_entry(
                        interaction.guild.id, "report_alert_channel"
                    )
                )
            )
        except TypeError:
            alert_channel = None

        if not alert_channel:
            user_embed = auxiliary.prepare_deny_embed(
                message="An error occurred while processing your report. It was not sent."
            )
            await interaction.response.send_message(embed=user_embed, ephemeral=True)
            return

        role = interaction.guild.get_role(
            int(
                configuration.get_config_entry(interaction.guild.id, "report_ping_role")
            )
        )

        await alert_channel.send(
            content=role.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        for index, user in enumerate(mentioned_users):
            await modlog.log_action(
                bot=self.bot,
                action_type="reported",
                guild=interaction.guild,
                reason=reason,
                member=user,
            )

        user_embed = auxiliary.prepare_confirm_embed(
            message="Your report was successfully sent"
        )
        await interaction.response.send_message(embed=user_embed, ephemeral=True)
