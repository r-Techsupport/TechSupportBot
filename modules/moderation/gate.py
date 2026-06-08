"""Module for defining the gate extension for the bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from discord.ext import commands

import configuration
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Gate plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(ServerGate(bot=bot))


class ServerGate(cogs.MatchCog):
    """Class to get the server gate from config."""

    async def match(self: Self, ctx: commands.Context, _: str) -> bool:
        """Matches any message and checks if it is in the gate channel

        Args:
            ctx (commands.Context): The context of the original message

        Returns:
            bool: Whether the message should be subject to the gate policy or not
        """
        channel = configuration.get_config_entry(ctx.guild.id, "gate_channel")
        if not channel:
            return False

        return ctx.channel.id == int(channel)

    async def response(
        self: Self, ctx: commands.Context, content: str, _: bool
    ) -> None:
        """Prepares a response to the gate policy,
            deleting the message and assigning roles if needed

        Args:
            ctx (commands.Context): The context of the message that triggered the gate
            content (str): The string contents of the message from the gate channel
        """
        is_admin = await self.bot.is_bot_admin(ctx.author)

        if is_admin:
            return

        await ctx.message.delete()

        if content.lower() == configuration.get_config_entry(
            ctx.guild.id, "gate_verify_text"
        ):
            roles = await self.get_roles(ctx)
            if not roles:
                log_channel = configuration.get_config_entry(
                    ctx.guild.id, "core_logging_channel"
                )
                await self.bot.logger.send_log(
                    message=(
                        "No roles to give user in gate plugin channel - ignoring"
                        " message"
                    ),
                    level=LogLevel.WARNING,
                    context=LogContext(guild=ctx.guild, channel=ctx.channel),
                    channel=log_channel,
                )
                return

            await ctx.author.add_roles(*roles, reason="Gate passed successfully")

            welcome_message = configuration.get_config_entry(
                ctx.guild.id, "gate_welcome_message"
            )
            delete_wait = configuration.get_config_entry(
                ctx.guild.id, "gate_delete_wait"
            )

            embed = auxiliary.generate_basic_embed(
                title="Server Gate",
                description=welcome_message,
                color=discord.Color.green(),
            )
            embed.set_footer(
                text=f"This message will be deleted in {delete_wait} seconds"
            )
            await ctx.send(
                embed=embed,
                delete_after=float(delete_wait),
            )

    async def get_roles(self: Self, ctx: commands.Context) -> list[discord.Role]:
        """Builds a list of roles that the user in ctx doesn't have,
            but are listed in the gate config roles to be applied

        Args:
            ctx (commands.Context): The context of the message that triggered the gate

        Returns:
            list[discord.Role]: A list of all the roles that should be given to the user
        """
        roles = []
        for role_name in configuration.get_config_entry(ctx.guild.id, "gate_roles"):
            role = discord.utils.get(ctx.guild.roles, name=role_name)

            if role in ctx.author.roles:
                continue

            if role:
                roles.append(role)

        return roles

    @commands.group(
        name="gate",
        brief="Executes a gate command",
        description="Executes a gate command",
    )
    async def gate_command(self: Self, ctx: commands.Context) -> None:
        """The bare .gate command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        return

    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    @gate_command.command(
        name="intro",
        brief="Generates a gate intro message",
        description="Generates the configured gate intro message",
    )
    async def intro_message(self: Self, ctx: commands.Context) -> None:
        """Admin only, generates a simple message that tells people how to use the gate channel
        It will print the intro_message config value

        Args:
            ctx (commands.Context): The context in which the command occured
        """
        if ctx.channel.id != int(
            configuration.get_config_entry(ctx.guild.id, "gate_channel")
        ):
            await auxiliary.send_deny_embed(
                message="That command is only usable in the gate channel",
                channel=ctx.channel,
            )
            return

        await ctx.channel.send(
            configuration.get_config_entry(ctx.guild.id, "gate_intro_message")
        )
