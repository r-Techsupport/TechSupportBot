"""
Module for the burn command on discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""
import random

import base
import discord
import util
from discord.ext import commands


async def setup(bot):
    """Method to add burn command to config."""
    await bot.add_cog(Burn(bot=bot))


class Burn(base.BaseCog):
    """Class for Burn command on the discord bot."""

    SEARCH_LIMIT = 50
    PHRASES = [
        "Sick BURN!",
        "Someone is going to need ointment for that BURN!",
        "Fire! Call 911! Someone just got BURNED!",
        "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOH BURN!",
        "BURN ALERT!",
        "Was that message a hot pan? BECAUSE IT BURNS!",
    ]

    def generate_burn_embed(self) -> discord.Embed:
        """
        This generates a burn embed properly styled

        Returns:
            discord.Embed: The styled embed, fully ready for sending
        """
        embed = discord.Embed(title="Burn Alert!")
        embed.color = discord.Color.red()
        message = random.choice(self.PHRASES)
        embed.description = f"🔥🔥🔥 {message} 🔥🔥🔥"
        return embed

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

        embed = self.generate_burn_embed()
        await ctx.send(embed=embed, targets=[user])

    async def get_message(
        self, ctx, prefix: str, user: discord.Member
    ) -> discord.Message:
        """Gets a message from the channel history to burn

        Args:
            ctx (commands.Context): The context in which the burn command was run in
            prefix (str): The current bot prefix. This is used to ignore command messages
            user (discord.Member): The member to search for a message from

        Returns:
            str: The matched message. Will be None if no message exists within the SEARCH_LIMT
        """
        matched_message = None

        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user and not message.content.startswith(prefix):
                matched_message = message
                break
        return matched_message

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
        message = await self.get_message(ctx, prefix, user_to_match)

        await self.handle_burn(ctx, user_to_match, message)
