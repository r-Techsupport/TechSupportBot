from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adds the cog to the bot. Setups config

    Args:
        bot (bot.TechSupportBot): The bot object to register the cog with
    """
    await bot.add_cog(Purger(bot=bot))


class Purger(cogs.BaseCog):
    ALERT_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/2063/PNG/512/"
        + "alert_danger_warning_notification_icon_124692.png"
    )

    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.group(
        brief="Executes a purge command",
        description="Executes a purge command",
    )
    async def purge(self, ctx):
        """Method to purge messages in discord."""
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @purge.command(
        name="amount",
        aliases=["x"],
        brief="Purges messages by amount",
        description="Purges the current channel's messages based on amount",
        usage="[amount]",
    )
    async def purge_amount(self, ctx: commands.context, amount: int = 1):
        """Method to get the amount to purge messages in discord."""
        config = self.bot.guild_configs[str(ctx.guild.id)]

        if amount <= 0 or amount > config.extensions.protect.max_purge_amount.value:
            amount = config.extensions.protect.max_purge_amount.value

        await ctx.channel.purge(limit=amount + 1)

        await self.send_alert(config, ctx, "Purge command")

    @purge.command(
        name="duration",
        aliases=["d"],
        brief="Purges messages by duration",
        description="Purges the current channel's messages up to a time",
        usage="[duration (minutes)]",
    )
    async def purge_duration(self, ctx, duration_minutes: int):
        """Method to purge a channel's message up to a time."""
        if duration_minutes < 0:
            await auxiliary.send_deny_embed(
                message="I can't use that input", channel=ctx.channel
            )
            return

        timestamp = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=duration_minutes
        )

        config = self.bot.guild_configs[str(ctx.guild.id)]

        await ctx.channel.purge(
            after=timestamp, limit=config.extensions.protect.max_purge_amount.value
        )

        await self.send_alert(config, ctx, "Purge command")

    async def send_alert(self, config, ctx: commands.Context, message: str):
        """Method to send an alert to the channel about a protect command."""
        try:
            alert_channel = ctx.guild.get_channel(
                int(config.extensions.protect.alert_channel.value)
            )
        except TypeError:
            alert_channel = None

        if not alert_channel:
            return

        embed = discord.Embed(title="Protect Alert", description=message)

        if len(ctx.message.content) >= 256:
            message_content = ctx.message.content[0:256]
        else:
            message_content = ctx.message.content

        embed.add_field(name="Channel", value=f"#{ctx.channel.name}")
        embed.add_field(name="User", value=ctx.author.mention)
        embed.add_field(name="Message", value=message_content, inline=False)
        embed.add_field(name="URL", value=ctx.message.jump_url, inline=False)

        embed.set_thumbnail(url=self.ALERT_ICON_URL)
        embed.color = discord.Color.red()

        await alert_channel.send(embed=embed)
