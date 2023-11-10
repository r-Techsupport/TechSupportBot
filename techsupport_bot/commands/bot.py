import re

import discord
import git
from base import cogs
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(BotInfo(bot=bot))


class BotInfo(cogs.BaseCog):
    ADMIN_ONLY = True

    @commands.command(name="bot", description="Provides bot info")
    async def get_bot_data(self, ctx):
        """Gets various data about the bot.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
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
        irc_config = getattr(self.bot.file_config.api, "irc")
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
