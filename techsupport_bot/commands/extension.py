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

import json
from typing import TYPE_CHECKING, Self

import discord
import ui
from core import auxiliary, cogs
from discord import app_commands
from discord.ext import commands

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
        extension_app_command_group (app_commands.Group): The group for the /extension commands
    """

    extension_app_command_group: app_commands.Group = app_commands.Group(
        name="extension", description="...", extras={"module": "extension"}
    )

    @extension_app_command_group.command(
        name="list_disabled",
        description="Lists all disabled extensions in the current server",
        extras={"module": "extension"},
    )
    async def list_disabled(self: Self, interaction: discord.Interaction) -> None:
        """This will read the current guild config and list all the
        extensions that are currently disabled

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        config = self.bot.guild_configs[str(interaction.guild.id)]
        missing_extensions = [
            item
            for item in self.bot.extension_name_list
            if item not in config.enabled_extensions
        ]
        if len(missing_extensions) == 0:
            embed = auxiliary.prepare_confirm_embed(
                message="No currently loaded extensions are disabled"
            )
        else:
            embed = auxiliary.prepare_confirm_embed(
                message=f"Disabled extensions: {missing_extensions}"
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_permissions(administrator=True)
    @extension_app_command_group.command(
        name="enable_all",
        description="Enables all loaded but disabled extensions in the guild",
        extras={"module": "extension"},
    )
    async def enable_everything(self: Self, interaction: discord.Interaction) -> None:
        """This will get all the disabled extensions and enable them for the current
        guild.

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        config = self.bot.guild_configs[str(interaction.guild.id)]
        missing_extensions = [
            item
            for item in self.bot.extension_name_list
            if item not in config.enabled_extensions
        ]
        if len(missing_extensions) == 0:
            embed = auxiliary.prepare_confirm_embed(
                message="No currently loaded extensions are disabled"
            )
        else:
            for extension in missing_extensions:
                config.enabled_extensions.append(extension)

            config.enabled_extensions.sort()
            # Modify the database
            await self.bot.write_new_config(
                str(interaction.guild.id), json.dumps(config)
            )

            # Modify the local cache
            self.bot.guild_configs[str(interaction.guild.id)] = config

            embed = auxiliary.prepare_confirm_embed(
                f"I have enabled {len(missing_extensions)} for this guild."
            )
        await interaction.response.send_message(embed=embed)

    @commands.check(auxiliary.bot_admin_check_context)
    @commands.group(
        name="extension",
        brief="Executes an extension bot command",
        description="Executes an extension bot command",
    )
    async def extension_group(self: Self, ctx: commands.Context) -> None:
        """The bare .extension command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @extension_group.command(
        name="status",
        description="Gets the status of an extension by name",
        usage="[extension-name]",
    )
    async def extension_status(
        self: Self, ctx: commands.Context, *, extension_name: str
    ) -> None:
        """Gets the status of an extension.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
            extension_name (str): the name of the extension
        """
        extensions_status = (
            "loaded"
            if ctx.bot.extensions.get(
                f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
            )
            else "unloaded"
        )
        functions_status = (
            "loaded"
            if ctx.bot.extensions.get(f"{self.bot.FUNCTIONS_DIR_NAME}.{extension_name}")
            else "unloaded"
        )
        embed = discord.Embed(
            title=f"Extension status for `{extension_name}`",
            description=f"Extension: {extensions_status}\nFunction: {functions_status}",
        )

        if functions_status == "loaded" or extensions_status == "loaded":
            embed.color = discord.Color.green()
        else:
            embed.color = discord.Color.gold()

        await ctx.send(embed=embed)

    @auxiliary.with_typing
    @extension_group.command(
        name="load", description="Loads an extension by name", usage="[extension-name]"
    )
    async def load_extension(
        self: Self, ctx: commands.Context, *, extension_name: str
    ) -> None:
        """Loads an extension by filename.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
            extension_name (str): the name of the extension
        """
        try:
            await ctx.bot.load_extension(f"functions.{extension_name}")
        except (ModuleNotFoundError, commands.errors.ExtensionNotFound):
            await ctx.bot.load_extension(f"commands.{extension_name}")
        await auxiliary.send_confirm_embed(
            message="I've loaded that extension", channel=ctx.channel
        )

    @auxiliary.with_typing
    @extension_group.command(
        name="unload",
        description="Unloads an extension by name",
        usage="[extension-name]",
    )
    async def unload_extension(
        self: Self, ctx: commands.Context, *, extension_name: str
    ) -> None:
        """Unloads an extension by filename.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
            extension_name (str): the name of the extension
        """
        try:
            await ctx.bot.unload_extension(f"functions.{extension_name}")
        except commands.errors.ExtensionNotLoaded:
            await ctx.bot.unload_extension(f"commands.{extension_name}")
        await auxiliary.send_confirm_embed(
            message="I've unloaded that extension", channel=ctx.channel
        )

    @auxiliary.with_typing
    @extension_group.command(
        name="register",
        description="Uploads an extension from Discord to be saved on the bot",
        usage="[extension-name] |python-file-upload|",
    )
    async def register_extension(
        self: Self, ctx: commands.Context, extension_name: str
    ) -> None:
        """Unloads an extension by filename.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
            extension_name (str): the name of the extension
        """
        if not ctx.message.attachments:
            await auxiliary.send_deny_embed(
                message="You did not provide a Python file upload", channel=ctx.channel
            )
            return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith(".py"):
            await auxiliary.send_deny_embed(
                message="I don't recognize your upload as a Python file",
                channel=ctx.channel,
            )
            return

        if extension_name.lower() in await self.bot.get_potential_extensions():
            view = ui.Confirm()
            await view.send(
                message=f"Warning! This will replace the current `{extension_name}.py` "
                + "extension! Are you SURE?",
                channel=ctx.channel,
                author=ctx.author,
            )
            await view.wait()

            if view.value is ui.ConfirmResponse.TIMEOUT:
                return
            if view.value is ui.ConfirmResponse.DENIED:
                await auxiliary.send_deny_embed(
                    message=f"{extension_name}.py was not replaced", channel=ctx.channel
                )
                return

        fp = await attachment.read()
        await self.bot.register_file_extension(extension_name, fp)
        await auxiliary.send_confirm_embed(
            message="I've registered that extension. You can now try loading it",
            channel=ctx.channel,
        )
