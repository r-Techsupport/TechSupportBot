"""
Commands which allow information about the bot to be shown
The cog in the file is named:
    BotInfo

This file contains 1 command:
    .bot
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Self

import discord
import git
from core import auxiliary, cogs
from discord.ext import commands

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

    @commands.check(auxiliary.bot_admin_check_context)
    @commands.command(name="bot", description="Provides bot info")
    async def get_bot_data(self: Self, ctx: commands.Context) -> None:
        """Gets various data about the bot.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the calling message
        """
        embed = discord.Embed(title=self.bot.user.name, color=discord.Color.blurple())

        embed.add_field(
            name="Started",
            value=f"{self.bot.startup_time} UTC" if self.bot.startup_time else "None",
            inline=True,
        )
        embed.add_field(
            name="Latency",
            value=f"{self.bot.latency*1000} ms" if self.bot.latency else "None",
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
                inline=True,
            )
        try:
            repo = git.Repo(search_parent_directories=True)
            commit = repo.head.commit
            commit_hash = commit.hexsha[:7]
            commit_message = commit.message.splitlines()[0].strip()
            branch_name = repo.active_branch.name
            match = re.search(
                r"github.com[:/](.*?)/(.*?)(?:.git)?$", repo.remotes.origin.url
            )
            if match:
                repo_owner = match.group(1)
                repo_name = match.group(2)
            else:
                repo_owner = ""
                repo_name = ""

            has_differences = repo.is_dirty()

            embed.add_field(
                name="Version Info",
                value=(
                    f"Upstream: `{repo_owner}/{repo_name}/{branch_name}`\n"
                    f"Commit: `{commit_hash} - {commit_message}`\n"
                    f"Local changes made: `{has_differences}`"
                ),
                inline=False,
            )
        except Exception as exc:
            embed.add_field(
                name="Version Info",
                value=f"There was an error getting version info: {exc}",
                inline=False,
            )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await ctx.send(embed=embed)
