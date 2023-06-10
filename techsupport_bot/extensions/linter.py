"""
Name: Linter
Info: Validates .json file syntax
Unit tests: None
Config: None
API: None
Databases: None
Models: None
Subcommands: None
Defines: check_syntax
"""
import json

import base
import discord
import util
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
    async def lint(self, ctx):
        """Method to add the lint command to the discord bot.
        Args:
            ctx (commands.Context) - Context to get the file from.
        """
        if len(ctx.message.attachments) != 1 or not ctx.message.attachments[
            0
        ].filename.endswith(".json"):
            await ctx.send_deny_embed("You need to attach a single .json file")
            return

        res = await self.check_syntax(ctx.message)
        if res:
            await ctx.send_deny_embed(f"Invalid syntax!\nError thrown: `{res}`")
            return

        await ctx.send_confirm_embed("Syntax is OK")
