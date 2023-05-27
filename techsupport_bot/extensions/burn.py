"""
Module for the burn command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""
import random

import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add burn command to config."""
    await bot.add_cog(Burn(bot=bot))


class Burn(base.BaseCog):
    """Class for Burn command on the discord bot."""

    PHRASES = [
        "Sick BURN!",
        "Someone is going to need ointment for that BURN!",
        "Fire! Call 911! Someone just got BURNED!",
        "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOH BURN!",
        "BURN ALERT!",
        "Was that message a hot pan? BECAUSE IT BURNS!",
    ]

    async def handle_burn(
        self, ctx, user: discord.Member, message: discord.Message
    ) -> None:
        """The core logic to handle the burn command

        Args:
            ctx (commands.Context): The context in which the command was run in
            user (discord.Member): The user that was called in the burn command
            message (discord.Message): The message to react to.
                Will be None if no message could be found

        Error handling:
            No message found: send_deny_embed
        """
        if not message:
            await ctx.send_deny_embed("I could not a find a message to reply to")
            return

        for emoji in ["🔥", "🚒", "👨‍🚒"]:
            await message.add_reaction(emoji)

        embed = auxiliary.generate_basic_embed(
            title="Burn Alert!",
            description=f"🔥🔥🔥 {random.choice(self.PHRASES)} 🔥🔥🔥",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed, targets=[user])

    @util.with_typing
    @commands.guild_only()
    @commands.command(
        brief="Declares a BURN!",
        description="Declares the user's last message as a BURN!",
        usage="@user",
    )
    async def burn(self, ctx, user_to_match: discord.Member):
        """The function executed when .burn is run on discord
        This is a command and should be accessed via discord

        Args:
            ctx (commands.Context): The context in which the command was run
            user_to_match (discord.Member): The user in which to burn
        """

        prefix = await self.bot.get_prefix(ctx.message)
        message = await auxiliary.search_channel_for_message(
            channel=ctx.channel, prefix=prefix, member_to_match=user_to_match
        )

        await self.handle_burn(ctx, user_to_match, message)
