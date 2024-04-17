"""
Module for the burn command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Burn plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Burn(bot=bot))


class Burn(cogs.BaseCog):
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
        self: Self,
        ctx: commands.Context,
        user: discord.Member,
        message: discord.Message,
    ) -> None:
        """The core logic to handle the burn command

        Args:
            ctx (commands.Context): The context in which the command was run in
            user (discord.Member): The user that was called in the burn command
            message (discord.Message): The message to react to.
                Will be None if no message could be found
        """
        if not message:
            await auxiliary.send_deny_embed(
                message="I could not a find a message to reply to", channel=ctx.channel
            )
            return

        await auxiliary.add_list_of_reactions(
            message=message, reactions=["🔥", "🚒", "👨‍🚒"]
        )

        embed = auxiliary.generate_basic_embed(
            title="Burn Alert!",
            description=f"🔥🔥🔥 {random.choice(self.PHRASES)} 🔥🔥🔥",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed, content=auxiliary.construct_mention_string([user]))

    async def burn_command(
        self, ctx: commands.Context, user_to_match: discord.Member
    ) -> None:
        """This the core logic of the burn command
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

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.command(
        brief="Declares a BURN!",
        description="Declares the user's last message as a BURN!",
        usage="@user",
    )
    async def burn(self, ctx: commands.Context, user_to_match: discord.Member) -> None:
        """The only purpose of this function is to accept input from discord

        Args:
            ctx (commands.Context): The context in which the command was run
            user_to_match (discord.Member): The user in which to burn
        """
        await self.burn_command(ctx, user_to_match)
