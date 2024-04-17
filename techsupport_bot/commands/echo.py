"""
Commands which allow admins to echo messages from the bot
The cog in the file is named:
    MessageEcho

This file contains 2 commands:
    .echo user
    .echo channel
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Echo plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(MessageEcho(bot=bot))


class MessageEcho(cogs.BaseCog):
    """
    The class that holds the echo commands
    """

    @commands.check(auxiliary.bot_admin_check_context)
    @commands.group(
        brief="Executes an echo bot command", description="Executes an echo bot command"
    )
    async def echo(self: Self, ctx: commands.Context) -> None:
        """The bare .echo command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @echo.command(
        name="channel",
        description="Echos a message to a channel",
        usage="[channel-id] [message]",
    )
    async def echo_channel(
        self, ctx: commands.Context, channel_id: int, *, message: str
    ) -> None:
        """Sends a message to a specified channel.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
            channel_id (int): the ID of the channel to send the echoed message
            message (str): the message to echo
        """
        channel = self.bot.get_channel(channel_id)
        if not channel:
            await auxiliary.send_deny_embed(
                message="I couldn't find that channel", channel=ctx.channel
            )
            return

        await channel.send(content=message)

        await auxiliary.send_confirm_embed(message="Message sent", channel=ctx.channel)

    @auxiliary.with_typing
    @echo.command(
        name="user",
        description="Echos a message to a user",
        usage="[user-id] [message]",
    )
    async def echo_user(
        self, ctx: commands.Context, user_id: int, *, message: str
    ) -> None:
        """Sends a message to a specified user.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (commands.Context): the context object for the calling message
            user_id (int): the ID of the user to send the echoed message
            message (str): the message to echo
        """
        user = await self.bot.fetch_user(int(user_id))
        if not user:
            await auxiliary.send_deny_embed(
                message="I couldn't find that user", channel=ctx.channel
            )
            return

        await user.send(content=message)

        await auxiliary.send_confirm_embed(message="Message sent", channel=ctx.channel)
