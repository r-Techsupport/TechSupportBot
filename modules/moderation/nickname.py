"""
A listener which changes peoples nicknames on join
The cog in the file is named:
    AutoNickName

This file does not contain any commands
"""

from __future__ import annotations

import random
import re
import string
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands
from discord.ext import commands
from unidecode import unidecode

import configuration
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Auto Nickname plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(AutoNickName(bot=bot))


def format_username(username: str) -> str:
    """Formats a username to be all ascii and easily readable and pingable

    Args:
        username (str): The original users username

    Returns:
        str: The new username with all formatting applied
    """

    # Prepare a random string, just in case
    random_string = "".join(random.choice(string.ascii_letters) for _ in range(10))

    # Step 1 - Force all ascii
    username = unidecode(username)

    # Step 2 - Remove all markdown
    markdown_pattern = r"(\*\*|__|\*|_|\~\~|`|#+|-{3,}|\|{3,}|>)"
    username = re.sub(markdown_pattern, "", username)

    # Step 3 - Strip
    username = username.strip()

    # Step 4 - Fix dumb spaces
    username = re.sub(r"\s+", " ", username)
    username = re.sub(r"(\b\w) ", r"\1", username)

    # Step 5 - Start with letter
    match = re.search(r"[A-Za-z]", username)
    if match:
        username = username[match.start() :]
    else:
        username = ""

    # Step 6 - Length check
    if len(username) < 3 and len(username) > 0:
        username = f"{username}-USER-{random_string}"
    elif len(username) == 0:
        username = f"USER-{random_string}"
    username = username[:32]

    return username


class AutoNickName(cogs.MatchCog):
    """
    The class that holds the listener and functions to auto change peoples nicknames
    """

    async def match(self: Self, ctx: commands.Context, content: str) -> bool:
        """On every message, check if the authors nickname should be changed

        Args:
            ctx (commands.Context): The context that sent the message
            content (str): The content of the message

        Returns:
            bool: If the nickname needs to be changed or not
        """
        if not configuration.get_config_entry("nickname_enable_on_message"):
            return False
        modified_name = format_username(ctx.author.display_name)

        # If the name didn't change for the user, do nothing
        if modified_name == ctx.author.display_name:
            return False
        return True

    async def response(
        self: Self,
        ctx: commands.Context,
        content: str,
        result: bool,
    ) -> None:
        """Changes the nickname of a given user, on message

        Args:
            ctx (commands.Context): The context that sent the message
            content (str): The content of the message
            result (bool): The return value of the match function
        """
        # If user outranks bot, do nothing
        if ctx.message.author.top_role >= ctx.channel.guild.me.top_role:
            return

        modified_name = format_username(ctx.author.display_name)

        # If we need to change the username, do so
        if modified_name != ctx.author.display_name:
            await ctx.author.edit(nick=modified_name)
            try:
                await ctx.author.send(
                    "Your nickname has been changed to make it easy to read and"
                    f" ping your name. Your new nickname is {modified_name}."
                )
            except discord.Forbidden:
                channel = configuration.get_config_entry(
                    ctx.guild.id, "core_logging_channel"
                )
                await self.bot.logger.send_log(
                    message=f"Could not DM {ctx.author.name} about nickname changes",
                    level=LogLevel.WARNING,
                    channel=channel,
                    context=LogContext(guild=ctx.author.guild),
                )

    @app_commands.checks.has_permissions(manage_nicknames=True)
    @app_commands.command(
        name="nicknamefix",
        description="Auto adjusts a nickname of the given member",
    )
    async def fixnickname(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Manually adjusts someones nickname to comply with the nickname filter
        Does not send a DM

        Args:
            interaction (discord.Interaction): The interaction the command was called at
            member (discord.Member): The member to update the nickname for
        """
        if member.bot:
            embed = auxiliary.prepare_deny_embed("Bots don't get new nicknames")
            return
        new_nickname = format_username(member.display_name)
        if new_nickname == member.display_name:
            embed = auxiliary.prepare_deny_embed(
                f"{member.mention} doesn't need a new nickname"
            )
            await interaction.response.send_message(embed=embed)
            return
        await member.edit(
            nick=new_nickname,
            reason=f"Change nickname command, ran by {interaction.user}",
        )
        embed = auxiliary.prepare_confirm_embed(
            f"{member.mention} name changed to {new_nickname}"
        )
        await interaction.response.send_message(embed=embed)
        return

    @commands.Cog.listener()
    async def on_member_join(self: Self, member: discord.Member) -> None:
        """
        This starts the running of the auto nickname formatter
        See: https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join

        Args:
            member (discord.Member): The member who joined
        """
        # Don't do anything if the filter is off for the guild
        if not configuration.get_config_entry(member.guild.id, "core_nickname_filter"):
            return

        modified_name = format_username(member.display_name)

        # If the name didn't change for the user, do nothing
        if modified_name == member.display_name:
            return

        await member.edit(nick=modified_name)
        try:
            await member.send(
                "Your nickname has been changed to make it easy to read and"
                f" ping your name. Your new nickname is {modified_name}."
            )
        except discord.Forbidden:
            channel = configuration.get_config_entry(
                member.guild.id, "core_logging_channel"
            )
            await self.bot.logger.send_log(
                message=f"Could not DM {member.name} about nickname changes",
                level=LogLevel.WARNING,
                channel=channel,
                context=LogContext(guild=member.guild),
            )
