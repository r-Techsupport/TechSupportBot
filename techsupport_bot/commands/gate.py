"""Module for defining the gate extension for the bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import munch
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Gate plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="channel",
        datatype="int",
        title="Server Gate Channel ID",
        description="The ID of the channel the gate is in",
        default=None,
    )
    config.add(
        key="roles",
        datatype="list",
        title="Roles to add",
        description="The list of roles to add after user is verified",
        default=[],
    )
    config.add(
        key="intro_message",
        datatype="str",
        title="Server Gate intro message",
        description="The message that's sent when running the intro message command",
        default=(
            "Welcome to our server! 👋 Please read the rules then type agree below to"
            " verify yourself"
        ),
    )
    config.add(
        key="welcome_message",
        datatype="str",
        title="Server Gate welcome message",
        description="The message to send to the user after they are verified",
        default="You are now verified! Welcome to the server!",
    )
    config.add(
        key="delete_wait",
        datatype="int",
        title="Welcome message delete time",
        description=(
            "The amount of time to wait (in seconds) before deleting the welcome"
            " message"
        ),
        default=60,
    )
    config.add(
        key="verify_text",
        datatype="str",
        title="Verification text",
        description=(
            "The case-insensitive text the user should type to verify themselves"
        ),
        default="agree",
    )

    await bot.add_cog(ServerGate(bot=bot, extension_name="gate"))
    bot.add_extension_config("gate", config)


class ServerGate(cogs.MatchCog):
    """Class to get the server gate from config."""

    async def match(
        self: Self, config: munch.Munch, ctx: commands.Context, _: str
    ) -> bool:
        """Matches any message and checks if it is in the gate channel

        Args:
            config (munch.Munch): The config for the guild where the message was sent
            ctx (commands.Context): The context of the original message

        Returns:
            bool: Whether the message should be subject to the gate policy or not
        """
        if not config.extensions.gate.channel.value:
            return False

        return ctx.channel.id == int(config.extensions.gate.channel.value)

    async def response(
        self: Self, config: munch.Munch, ctx: commands.Context, content: str, _: bool
    ) -> None:
        """Prepares a response to the gate policy,
            deleting the message and assigning roles if needed

        Args:
            config (munch.Munch): The config of the guild with the gate
            ctx (commands.Context): The context of the message that triggered the gate
            content (str): The string contents of the message from the gate channel
        """
        is_admin = await self.bot.is_bot_admin(ctx.author)

        if is_admin:
            return

        await ctx.message.delete()

        if content.lower() == config.extensions.gate.verify_text.value:
            roles = await self.get_roles(config, ctx)
            if not roles:
                config = self.bot.guild_configs[str(ctx.guild.id)]
                log_channel = config.get("logging_channel")
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

            welcome_message = config.extensions.gate.welcome_message.value
            delete_wait = config.extensions.gate.delete_wait.value

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

    async def get_roles(
        self: Self, config: munch.Munch, ctx: commands.Context
    ) -> list[discord.Role]:
        """Builds a list of roles that the user in ctx doesn't have,
            but are listed in the gate config roles to be applied

        Args:
            config (munch.Munch): The config of the guild
            ctx (commands.Context): The context of the message that triggered the gate

        Returns:
            list[discord.Role]: A list of all the roles that should be given to the user
        """
        roles = []
        for role_name in config.extensions.gate.roles.value:
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

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

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
        config = self.bot.guild_configs[str(ctx.guild.id)]

        if ctx.channel.id != int(config.extensions.gate.channel.value):
            await auxiliary.send_deny_embed(
                message="That command is only usable in the gate channel",
                channel=ctx.channel,
            )
            return

        await ctx.channel.send(config.extensions.gate.intro_message.value)
