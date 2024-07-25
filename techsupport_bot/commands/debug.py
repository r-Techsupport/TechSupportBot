"""The channel slowmode modification extension
Holds only a single slash command"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Registers the slowmode cog

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(Debugger(bot=bot))


class Debugger(cogs.BaseCog):
    """The cog that holds the slowmode commands and helper functions

    Attrs:
        debug_group (app_commands.Group): The group for the /debug commands
    """

    debug_group = app_commands.Group(
        name="debug", description="...", extras={"module": "debug"}
    )

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @debug_group.command(
        name="message",
        description="Searches and displays all the message properties",
        extras={
            "module": "debug",
        },
    )
    async def debug_message(
        self: Self,
        interaction: discord.Interaction,
        channel: discord.abc.GuildChannel,
        id: str,
    ) -> None:
        """Modifies slowmode on a given channel

        Args:
            interaction (discord.Interaction): The interaction that called this command
            seconds (int): The seconds to change the slowmode to. 0 will disable slowmode
            channel (discord.abc.GuildChannel, optional): If specified, the channel to modify
                slowmode on. Defaults to the channel the command was invoked in.
        """
        message = await channel.fetch_message(str(id))
        properties_string = ""

        for attribute in dir(message):
            if not attribute.startswith("_"):
                value = getattr(message, attribute)
                temp_string = f"**{attribute}:** {value}\n"
                if temp_string.startswith(f"**{attribute}:** <bound method"):
                    continue
                properties_string += temp_string

        embed = discord.Embed(description=properties_string[:4000])
        await interaction.response.send_message(embed=embed)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @debug_group.command(
        name="member",
        description="Searches and displays all the member properties",
        extras={
            "module": "debug",
        },
    )
    async def debug_member(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Modifies slowmode on a given channel

        Args:
            interaction (discord.Interaction): The interaction that called this command
            seconds (int): The seconds to change the slowmode to. 0 will disable slowmode
            channel (discord.abc.GuildChannel, optional): If specified, the channel to modify
                slowmode on. Defaults to the channel the command was invoked in.
        """
        properties_string = ""

        for attribute in dir(member):
            if not attribute.startswith("_"):
                value = getattr(member, attribute)
                temp_string = f"**{attribute}:** {value}\n"
                if temp_string.startswith(f"**{attribute}:** <bound method"):
                    continue
                properties_string += temp_string

        embed = discord.Embed(description=properties_string[:4000])
        await interaction.response.send_message(embed=embed)
