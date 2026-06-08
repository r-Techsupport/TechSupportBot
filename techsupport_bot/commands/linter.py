"""
Name: Linter
Info: Validates .json file syntax
Unit tests: Yes
Config: None
API: None
Databases: None
Models: None
Subcommands: .lint
Defines: check_syntax
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
    """Loading the Linter plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Lint(bot=bot))


class Lint(cogs.BaseCog):
    """Class to add the lint command on the discord bot."""

    async def check_syntax(self: Self, message: discord.Message) -> str:
        """Checks if the json syntax is valid by trying to load it.

        Args:
            message (discord.Message): The message to check the json file of

        Returns:
            str: The thrown error
        """
        # The called method returns JSONDecodeError if the syntax is not valid.
        try:
            await auxiliary.get_json_from_attachments(message, as_string=True)
        except json.JSONDecodeError as err:
            return err

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.command(
        brief="Checks the syntax of an attached json file",
        description="Checks the syntax of an attached json file",
        usage="|json-file|",
    )
    async def lint(self: Self, ctx: commands.Context) -> None:
        """Method to add the lint command to the discord bot.

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        await self.lint_command(ctx)

    async def lint_command(self: Self, ctx: commands.Context) -> None:
        """The core logic for the lint command

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        if not self.check_valid_attachments(ctx.message.attachments):
            await auxiliary.send_deny_embed(
                message="You need to attach a single .json file", channel=ctx.channel
            )
            return

        res = await self.check_syntax(ctx.message)
        if res:
            await auxiliary.send_deny_embed(
                message=f"Invalid syntax!\nError thrown: `{res}`", channel=ctx.channel
            )
            return

        await auxiliary.send_confirm_embed(message="Syntax is OK", channel=ctx.channel)

    def check_valid_attachments(
        self: Self, attachments: list[discord.Attachment]
    ) -> bool:
        """A command to check if the attachments on a message are valid for linter

        Args:
            attachments (list[discord.Attachment]): A list of discord.Attachment

        Returns:
            bool: True if valid, False if invalid
        """
        if len(attachments) != 1 or not attachments[0].filename.endswith(".json"):
            return False
        return True
