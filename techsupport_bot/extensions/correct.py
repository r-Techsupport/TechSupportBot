"""
Module for the correct command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""
import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add correct to the config."""
    await bot.add_cog(Corrector(bot=bot))


class Corrector(base.BaseCog):
    """Class for the correct command for the discord bot."""

    async def correct_command(self, ctx, to_replace: str, replacement: str) -> None:
        """This is the main processing for the correct command

        Args:
            ctx (commands.Context): The context where the command was run
            to_replace (str): What substring is being asked to find a message with
            replacement (str): If a message with to_replace is found,
                this is what it will be replaced with
        """
        prefix = await self.bot.get_prefix(ctx.message)
        message_to_correct = await auxiliary.search_channel_for_message(
            channel=ctx.channel,
            prefix=prefix,
            content_to_match=to_replace,
            allow_bot=False,
        )
        if not message_to_correct:
            await auxiliary.send_deny_embed(
                message="I couldn't find any message to correct", channel=ctx.channel
            )
            return

        updated_message = self.prepare_message(
            message_to_correct.content, to_replace, replacement
        )
        embed = auxiliary.generate_basic_embed(
            title="Correction!",
            description=f"{updated_message} :white_check_mark:",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed, targets=[message_to_correct.author])

    def prepare_message(
        self, old_content: str, to_replace: str, replacement: str
    ) -> str:
        """This corrects a message based on input

        Args:
            old_content (str): The old content of the message to be corrected
            to_replace (str): What substring of the message needs to be replaced
            replacement (str): What string to replace to_replace with

        Returns:
            str: The corrected content
        """
        return old_content.replace(to_replace, f"**{replacement}**")

    @util.with_typing
    @commands.guild_only()
    @commands.command(
        aliases=["c"],
        brief="Corrects a message",
        description="Replaces the most recent text with your text",
        usage="[to_replace] [replacement]",
    )
    async def correct(self, ctx, to_replace: str, replacement: str):
        """Method for the correct command for the discord bot."""
        await self.correct_command(ctx, to_replace, replacement)
