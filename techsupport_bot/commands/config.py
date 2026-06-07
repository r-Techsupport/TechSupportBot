"""Module for config commands."""

from __future__ import annotations

import datetime
import io
import json
from typing import TYPE_CHECKING, Self

import configuration
import discord
import munch
import ui
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Guild Config plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(ConfigControl(bot=bot))


class ConfigControl(cogs.BaseCog):
    """Cog object for per-guild config control."""

    config_commands: app_commands.Group = app_commands.Group(
        name="config", description="...", extras={"module": "config"}
    )

    config_extension_commands: app_commands.Group = app_commands.Group(
        name="extension",
        description="...",
        extras={"module": "config"},
        parent=config_commands,
    )

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    @config_extension_commands.command(
        name="enable",
        description="Enables an extension for the guild by name",
        extras={"module": "config", "usage": "[extension-name]"},
    )
    async def enable_extension(
        self: Self, interaction: discord.Interaction, extension_name: str
    ) -> None:
        """Enables an extension for the guild.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            extension_name (str): the extension subname to enable
        """
        if extension_name not in self.bot.extension_name_list:
            embed = auxiliary.prepare_deny_embed(
                message=f"I could not find the extension {extension_name}",
            )
            await interaction.response.send_message(embed=embed)
            return

        extensions_list: list[str] = configuration.get_config_entry(
            interaction.guild.id, "core_enabled_extensions"
        )
        if extension_name in extensions_list:
            embed = auxiliary.prepare_deny_embed(
                message=f"The extension {extension_name} is already enabled for this guild",
            )
            await interaction.response.send_message(embed=embed)
            return

        extensions_list.append(extension_name)
        extensions_list.sort()

        configuration.edit_config_entry(
            interaction.guild.id, "core_enabled_extensions", extensions_list
        )

        embed = auxiliary.prepare_confirm_embed(
            message="I've enabled that extension for this guild"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    @config_extension_commands.command(
        name="disable",
        description="Disables an extension for the guild by name",
        extras={"module": "config", "usage": "[extension-name]"},
    )
    async def disable_extension(
        self: Self, interaction: discord.Interaction, extension_name: str
    ) -> None:
        """Disables an extension for the guild.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            extension_name (str): the extension subname to disable
        """
        if extension_name not in self.bot.extension_name_list:
            embed = auxiliary.prepare_deny_embed(
                message=f"I could not find the extension {extension_name}",
            )
            await interaction.response.send_message(embed=embed)
            return

        extensions_list: list[str] = configuration.get_config_entry(
            interaction.guild.id, "core_enabled_extensions"
        )
        if extension_name not in extensions_list:
            embed = auxiliary.prepare_deny_embed(
                message=f"The extension {extension_name} is already disabled for this guild",
            )
            await interaction.response.send_message(embed=embed)
            return

        extensions_list.remove(extension_name)
        extensions_list.sort()

        configuration.edit_config_entry(
            interaction.guild.id, "core_enabled_extensions", extensions_list
        )

        embed = auxiliary.prepare_confirm_embed(
            message="I've disabled that extension for this guild"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_permissions(administrator=True)
    @config_extension_commands.command(
        name="list-disabled",
        description="Lists all disabled extensions in the current server",
        extras={"module": "config"},
    )
    async def list_disabled(self: Self, interaction: discord.Interaction) -> None:
        """This will read the current guild config and list all the
        extensions that are currently disabled

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        extensions_list: list[str] = configuration.get_config_entry(
            interaction.guild.id, "core_enabled_extensions"
        )
        missing_extensions = [
            item for item in self.bot.extension_name_list if item not in extensions_list
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
    @config_extension_commands.command(
        name="enable-all",
        description="Enables all loaded but disabled extensions in the guild",
        extras={"module": "config"},
    )
    async def enable_everything(self: Self, interaction: discord.Interaction) -> None:
        """This will get all the disabled extensions and enable them for the current
        guild.

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        extensions_list: list[str] = configuration.get_config_entry(
            interaction.guild.id, "core_enabled_extensions"
        )
        missing_extensions = [
            item for item in self.bot.extension_name_list if item not in extensions_list
        ]
        if len(missing_extensions) == 0:
            embed = auxiliary.prepare_confirm_embed(
                message="No currently loaded extensions are disabled"
            )
        else:
            for extension in missing_extensions:
                extensions_list.append(extension)

            extensions_list.sort()
            # Modify the config
            configuration.edit_config_entry(
                interaction.guild.id, "core_enabled_extensions", extensions_list
            )

            embed = auxiliary.prepare_confirm_embed(
                f"I have enabled {len(missing_extensions)} extension(s) for this guild."
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_permissions(administrator=True)
    @config_commands.command(
        name="json",
        description="This gets the guild config json file and sends it as a response",
        extras={"module": "config"},
    )
    async def config_json(self: Self, interaction: discord.Interaction):
        """This pulls the guild json config and send it to the caller

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        try:
            json_config = configuration.get_guild_config_json(interaction.guild.id)
        except AttributeError:
            embed = auxiliary.prepare_deny_embed(
                "This guild has no current configuration"
            )
            await interaction.response.send_message(embed=embed)
            return
        json_file = discord.File(
            io.StringIO(json.dumps(json_config, indent=4)),
            filename=f"{interaction.guild.id}-config-{datetime.datetime.utcnow()}.json",
        )
        await interaction.response.send_message(file=json_file)

    @app_commands.checks.has_permissions(administrator=True)
    @config_commands.command(
        name="patch",
        description="Edits guild config by uploading JSON",
        extras={"module": "config", "usage": "[uploaded-json]"},
    )
    async def patch_config(
        self: Self, interaction: discord.Interaction, config_json: discord.Attachment
    ) -> None:
        """Takes the uploaded json file and writes it to disk

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        await interaction.response.defer()

        if not config_json.filename.endswith(".json"):
            embed = auxiliary.prepare_deny_embed(
                message="I don't recognize your upload as a json file",
            )
            await interaction.followup.send(embed=embed)
            return

        json_bytes: bytes = await config_json.read()
        json_data: munch.Munch = munch.munchify(json.loads(json_bytes.decode("utf-8")))

        configuration.write_guild_config_json(interaction.guild.id, json_data)

        embed = auxiliary.prepare_confirm_embed("I have updated this guilds config")
        await interaction.followup.send(embed=embed)

    @app_commands.checks.has_permissions(administrator=True)
    @config_commands.command(
        name="reset",
        description="Resets config to default for the current guild",
        extras={"module": "config"},
    )
    async def reset_config(self: Self, interaction: discord.Interaction) -> None:
        """A function to reset the current guild config to stock

        Args:
            interaction (discord.Interaction): The interaction that triggered the slash command
        """
        view = ui.Confirm()
        await view.send(
            message=f"Are you sure you want to reset the config for {interaction.guild.name}?",
            author=interaction.user,
            interaction=interaction,
        )
        await view.wait()
        if view.value == ui.ConfirmResponse.DENIED:
            embed = auxiliary.prepare_deny_embed(
                message="The config was not reset",
            )
            await view.followup.send(embed=embed)
            return
        if view.value == ui.ConfirmResponse.TIMEOUT:
            return

        default_config = configuration.get_default_config_json()
        default_config.core_guild_id = interaction.guild.id

        configuration.write_guild_config_json(interaction.guild.id, default_config)

        embed = auxiliary.prepare_confirm_embed(
            message="I've reset the config for this guild"
        )
        view.followup.send(embed=embed)
