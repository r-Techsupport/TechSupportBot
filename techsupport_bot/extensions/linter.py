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
import json

import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add the lint command to the bot config"""
    await bot.add_cog(Lint(bot=bot))


class Lint(base.BaseCog):
    """Class to add the lint command on the discord bot."""

    async def check_syntax(self, message: discord.Message) -> str:
        """Checks if the json syntax is valid by trying to load it.
        Args:
            message (discord.Message) - The message to check the json file of

        Returns:
            (str) - The thrown error
        """
        # The called method returns JSONDecodeError if the syntax is not valid.
        try:
            await util.get_json_from_attachments(message, as_string=True)
        except json.JSONDecodeError as err:
            return err

    @util.with_typing
    @commands.guild_only()
    @commands.command(
        brief="Checks the syntax of an attached json file",
        description="Checks the syntax of an attached json file",
        usage="|json-file|",
    )
    async def lint(self, ctx: commands.Context):
        """Method to add the lint command to the discord bot.
        Args:
            ctx (commands.Context) - The context in which the command was run
        """
        await self.lint_command(ctx)

    async def lint_command(self, ctx: commands.Context):
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

    def check_valid_attachments(self, attachments: list) -> bool:
        """A command to check if the attachments on a message are valid for linter

        Args:
            attachments (list): A list of discord.Attachment

        Returns:
            bool: True if valid, False if invalid
        """
        if len(attachments) != 1 or not attachments[0].filename.endswith(".json"):
            return False
        return True
