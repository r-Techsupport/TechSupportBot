"""
Commands which allows the admin to create github issues on linked repo
The cog in the file is named:
    IssueCreator

This file contains 4 commands:
    .botish
    .botissue
    .ish
    .issue
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Github plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """
    try:
        if not bot.file_config.api.github.api_key:
            raise AttributeError("IssueCreator was not loaded due to missing API key")
        if not bot.file_config.api.github.username:
            raise AttributeError("IssueCreator was not loaded due to missing API key")
        if not bot.file_config.api.github.repo:
            raise AttributeError("IssueCreator was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError(
            "IssueCreator was not loaded due to missing API key"
        ) from exc
    await bot.add_cog(IssueCreator(bot=bot))


class IssueCreator(cogs.BaseCog):
    """
    The class that holds the issue commands
    """

    GITHUB_API_BASE_URL = "https://api.github.com"

    @commands.check(auxiliary.bot_admin_check_context)
    @auxiliary.with_typing
    @commands.command(
        name="issue",
        aliases=["ish", "botish", "botissue"],
        description="Creates a Github issue on the configured bot repo",
        usage="[title] [description]",
    )
    async def issue(self: Self, ctx, title: str, description: str):
        """Creates an issue in the bot's Github Repo

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
            title: the title of the issue
            description: the description of the issue
        """

        if not self.bot.file_config.api.github.api_key:
            await auxiliary.send_deny_embed(
                message="I don't have a Github API key", channel=ctx.channel
            )
            return

        if (
            not self.bot.file_config.api.github.username
            or not self.bot.file_config.api.github.repo
        ):
            await auxiliary.send_deny_embed(
                message="I don't have a Github repo configured", channel=ctx.channel
            )
            return

        headers = {
            "Authorization": f"Bearer {self.bot.file_config.api.github.api_key}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "text/plain",
        }

        response = await self.bot.http_functions.http_call(
            "post",
            f"{self.GITHUB_API_BASE_URL}/repos/{self.bot.file_config.api.github.username}"
            + f"/{self.bot.file_config.api.github.repo}/issues",
            headers=headers,
            data=json.dumps({"title": title, "body": description}),
        )

        status_code = response.get("status_code")
        if status_code != 201:
            await auxiliary.send_deny_embed(
                message=(
                    f"I was unable to create your issue (status code {status_code})"
                ),
                channel=ctx.channel,
            )
            return

        issue_url = response.get("html_url")
        number = response.get("number")

        embed = discord.Embed(title="Issue Created", color=discord.Color.blurple())
        embed.add_field(name=f"Issue #{number}", value=f"{issue_url}")
        embed.set_thumbnail(
            url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
        )

        await ctx.send(embed=embed)
