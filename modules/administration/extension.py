"""
Commands which allow control over loaded extensions
The cog in the file is named:
    ExtensionControl

This file contains 4 commands:
    .extension status
    .extension load
    .extension unload
    .extension register
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import ui
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Extension Control plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(ExtensionControl(bot=bot))


class ExtensionControl(cogs.BaseCog):
    """
    The class that holds the extension commands

    Attributes:
        extension_commands (app_commands.Group): The group for the /extension commands
    """

    extension_commands: app_commands.Group = app_commands.Group(
        name="extension",
        description="...",
    )

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @extension_commands.command(
        name="status",
        description="Gets the status of an extension by name",
        extras={"usage": "[extension-name]"},
    )
    async def extension_status(
        self: Self, interaction: discord.Interaction, extension_name: str
    ) -> None:
        """Gets the status of an extension.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the interaction that called this command
            extension_name (str): the name of the extension
        """
        extensions_status = (
            "loaded"
            if self.bot.extensions.get(
                f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
            )
            else "unloaded"
        )

        embed = discord.Embed(
            title=f"Extension status for `{extension_name}`",
            description=f"{extensions_status}",
        )

        if extensions_status == "loaded":
            embed.color = discord.Color.green()
        else:
            embed.color = discord.Color.gold()

        await interaction.response.send_message(embed=embed)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @extension_commands.command(
        name="load",
        description="Loads an extension by name",
        extras={"usage": "[extension-name]"},
    )
    async def load_extension(
        self: Self, interaction: discord.Interaction, extension_name: str
    ) -> None:
        """Loads an extension by filename.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the interaction that called this command
            extension_name (str): the name of the extension
        """
        if not self.does_extension_exist:
            embed = auxiliary.prepare_deny_embed(f"I could not find {extension_name}")
            await interaction.response.send_message(embed=embed)
            return

        await self.bot.load_extension(
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
        )

        embed = auxiliary.prepare_confirm_embed(
            message=f"I've loaded the {extension_name} extension"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @extension_commands.command(
        name="unload",
        description="Unloads an extension by name",
        extras={"usage": "[extension-name]"},
    )
    async def unload_extension(
        self: Self, interaction: discord.Interaction, extension_name: str
    ) -> None:
        """Unloads an extension by filename.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the interaction that called this command
            extension_name (str): the name of the extension
        """
        if not self.does_extension_exist:
            embed = auxiliary.prepare_deny_embed(f"I could not find {extension_name}")
            await interaction.response.send_message(embed=embed)
            return

        await self.bot.unload_extension(
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
        )

        embed = auxiliary.prepare_confirm_embed(
            message=f"I've unloaded the {extension_name} extension"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @extension_commands.command(
        name="reload",
        description="Reloads an extension by name",
        extras={"usage": "[extension-name]"},
    )
    async def reload_extension(
        self: Self, interaction: discord.Interaction, extension_name: str
    ) -> None:
        """Unloads an extension by filename.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): the interaction that called this command
            extension_name (str): the name of the extension
        """
        if not self.does_extension_exist:
            embed = auxiliary.prepare_deny_embed(f"I could not find {extension_name}")
            await interaction.response.send_message(embed=embed)
            return

        await self.bot.unload_extension(
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
        )
        await self.bot.load_extension(
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
        )

        embed = auxiliary.prepare_confirm_embed(
            message=f"I've reloaded the {extension_name} extension"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @extension_commands.command(
        name="register",
        description="Uploads an extension from Discord to be saved on the bot",
        extras={
            "usage": "[extension-name] [python-file-upload]",
        },
    )
    async def register_extension(
        self: Self,
        interaction: discord.Interaction,
        extension_name: str,
        extension_file: discord.Attachment,
    ) -> None:
        """Registers an extension by filename.

        Args:
            interaction (discord.Interaction): the interaction that called this command
            extension_name (str): the name of the extension
            extension_file (discord.Attachment): The python file of the extension
        """
        await interaction.response.defer()
        if not extension_file.filename.endswith(".py"):
            embed = auxiliary.prepare_deny_embed(
                message="I don't recognize your upload as a Python file",
            )
            await interaction.followup.send(embed=embed)
            return

        if extension_name.lower() in await self.bot.get_potential_extensions():
            view = ui.Confirm()
            await view.send(
                message=f"Warning! This will replace the current `{extension_name}.py` "
                + "extension! Are you SURE?",
                channel=interaction.channel,
                author=interaction.user,
                interaction=interaction,
            )
            await view.wait()

            if view.value is ui.ConfirmResponse.TIMEOUT:
                return
            if view.value is ui.ConfirmResponse.DENIED:
                embed = auxiliary.send_deny_embed(
                    message=f"{extension_name}.py was not replaced"
                )
                await view.followup.send(embed=embed)
                return

        fp = await extension_file.read()
        await self.bot.register_file_extension(extension_name, fp)
        embed = auxiliary.prepare_confirm_embed(
            message="I've registered that extension. You can now try loading it",
        )
        await interaction.followup.send(embed=embed)
        return

    async def does_extension_exist(self: Self, extension_name: str) -> bool:
        """Checks if a specific extension by name exists

        Args:
            extension_name (str): The name of the extension to check

        Returns:
            bool: Whether or not this extensions exists in the bot
        """
        return extension_name in self.bot.extension_name_list
