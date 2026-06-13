"""The file that holds the honeypot function"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
from discord.ext import commands

import configuration
from core import cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(HoneyPot(bot=bot))


class HoneyPot(cogs.MatchCog):
    """The pasting module"""

    async def match(self: Self, ctx: commands.Context, content: str) -> bool:
        """Checks to see if a message was sent in a honeypot channel

        Args:
            ctx (commands.Context): The context of the original message
            content (str): The string representation of the message

        Returns:
            bool: Whether the author sent in a honeypot channel
        """
        # If the channel isn't a honeypot, do nothing.
        if not str(ctx.channel.id) in configuration.get_config_entry(
            ctx.guild.id, "honeypot_channels"
        ):
            return False
        return True

    async def response(
        self: Self,
        ctx: commands.Context,
        content: str,
        result: bool,
    ) -> None:
        """Handles a honeypot check

        Args:
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message
            result (bool): What the match() function returned
        """
        # Temporary ban and unban.
        # This should be replaced with a guild wide purge when discord.py can be updated.
        await ctx.author.ban(delete_message_days=1, reason="triggered honeypot")
        await ctx.guild.unban(ctx.author, reason="triggered honeypot")
        # Send an alert in the alert channel, if its configured
        try:
            alert_channel = ctx.guild.get_channel(
                configuration.get_config_entry(ctx.guild.id, "moderation_alert_channel")
            )
        except TypeError:
            alert_channel = None

        if not alert_channel:
            return

        embed = discord.Embed(title="Honeypot triggered")
        embed.add_field(
            name="Offending member",
            value=f"{ctx.author.global_name} ({ctx.author.name})",
        )
        embed.add_field(name="Message text", value=ctx.message.clean_content[:500])
        embed.add_field(
            name="Number of attachments", value=len(ctx.message.attachments)
        )
        embed.color = discord.Color.red()
        embed.timestamp = datetime.datetime.utcnow()

        embed.set_footer(
            text=f"Author ID: {ctx.author.id} • Message ID: {ctx.message.id}"
        )

        await alert_channel.send(embed=embed)

        # Get only message in the channel and edit the description
        # Just in case, we make sure we pick the first message in the channel, as a foolproof method
        history = ctx.channel.history(oldest_first=True, limit=1)
        starting_message = await anext(history)
        starting_embed = starting_message.embeds[0]
        new_actions = int(starting_embed.description.split(":")[1]) + 1
        starting_embed.description = (
            f"{starting_embed.description.split(':')[0]}: {new_actions}"
        )

        await starting_message.edit(embeds=[starting_embed])
