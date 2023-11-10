"""Module for config commands.
"""

import datetime
import io
import json

import discord
import ui
from base import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Method to add burn command to config."""
    await bot.add_cog(ConfigControl(bot=bot))


class ConfigControl(cogs.BaseCog):
    """Cog object for per-guild config control."""

    @commands.group(
        name="config",
        brief="Issues a config command",
        description="Issues a config command",
    )
    async def config_command(self, ctx):
        """The parent config command.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """

        # Executed if there are no/invalid args supplied
        def get_help_embed(self, command_prefix):
            # Gets commands, checks if first supplied arg is valid
            embed = discord.Embed(
                title="Incorrect/no args provided, correct command usage:"
            )

            # Loops through each command in this cog
            for command in self.bot.get_cog(self.qualified_name).walk_commands():
                if issubclass(command.__class__, commands.Group):
                    continue

                if command.full_parent_name == "":
                    syntax = f"{command_prefix}{command.name}"

                else:
                    syntax = (
                        f"{command_prefix}{command.full_parent_name} {command.name}"
                    )

                embed.color = discord.Color.green()
                embed.add_field(
                    name=f"`{syntax} {command.usage or ''}`",
                    value=command.description or "No description available",
                    inline=False,
                )

            return embed

        # Checks if no arguments were supplied
        if len(ctx.message.content.split()) < 2:
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

        # Checks whether the first given argument is valid if more than one argument is supplied
        elif ctx.message.content.split().pop(1) not in [
            command.name
            for command in self.bot.get_cog(self.qualified_name).walk_commands()
        ]:
            view = ui.Confirm()
            await view.send(
                message="Invalid argument! Show help command?",
                channel=ctx.channel,
                author=ctx.author,
                timeout=10,
            )
            await view.wait()
            if view.value != ui.ConfirmResponse.CONFIRMED:
                return

            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @config_command.command(
        name="patch",
        brief="Edits guild config",
        description="Edits guild config by uploading JSON",
        usage="|uploaded-json|",
    )
    async def patch_config(self, ctx):
        """Displays the current config to the user.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        config = self.bot.guild_configs[str(ctx.guild.id)]

        uploaded_data = await auxiliary.get_json_from_attachments(ctx.message)
        if uploaded_data:
            # server-side check of guild
            if str(ctx.guild.id) != str(uploaded_data["guild_id"]):
                await auxiliary.send_deny_embed(
                    message="This config file is not for this guild",
                    channel=ctx.channel,
                )
                return
            uploaded_data["guild_id"] = str(ctx.guild.id)
            config_difference = auxiliary.config_schema_matches(uploaded_data, config)
            if config_difference:
                view = ui.Confirm()
                await view.send(
                    message=f"Accept {config_difference} changes to the guild config?",
                    channel=ctx.channel,
                    author=ctx.author,
                )
                await view.wait()
                if view.value is ui.ConfirmResponse.DENIED:
                    await auxiliary.send_deny_embed(
                        message="Config was not changed",
                        channel=ctx.channel,
                    )
                if view.value is not ui.ConfirmResponse.CONFIRMED:
                    return

            # Modify the database
            await self.bot.write_new_config(
                str(ctx.guild.id), json.dumps(uploaded_data)
            )

            # Modify the local cache
            self.bot.guild_configs[str(ctx.guild.id)] = uploaded_data

            await auxiliary.send_confirm_embed(
                message="I've updated that config", channel=ctx.channel
            )
            return

        json_config = config.copy()

        json_config.pop("_id", None)

        json_file = discord.File(
            io.StringIO(json.dumps(json_config, indent=4)),
            filename=f"{ctx.guild.id}-config-{datetime.datetime.utcnow()}.json",
        )

        await ctx.send(file=json_file)

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @config_command.command(
        name="enable-extension",
        brief="Enables an extension",
        description="Enables an extension for the guild by name",
        usage="[extension-name]",
    )
    async def enable_extension(self, ctx, extension_name: str):
        """Enables an extension for the guild.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_name (str): the extension subname to enable
        """
        if not (
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}" in self.bot.extensions
            or f"{self.bot.FUNCTIONS_DIR_NAME}.{extension_name}" in self.bot.extensions
        ):
            await auxiliary.send_deny_embed(
                message="I could not find that extension, or it's not loaded",
                channel=ctx.channel,
            )
            return

        config = self.bot.guild_configs[str(ctx.guild.id)]
        if extension_name in config.enabled_extensions:
            await auxiliary.send_deny_embed(
                message="That extension is already enabled for this guild",
                channel=ctx.channel,
            )
            return

        config.enabled_extensions.append(extension_name)
        config.enabled_extensions.sort()

        # Modify the database
        await self.bot.write_new_config(str(ctx.guild.id), json.dumps(config))

        # Modify the local cache
        self.bot.guild_configs[str(ctx.guild.id)] = config

        await auxiliary.send_confirm_embed(
            message="I've enabled that extension for this guild", channel=ctx.channel
        )

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @config_command.command(
        name="disable-extension",
        brief="Disables an extension",
        description="Disables an extension for the guild by name",
        usage="[extension-name]",
    )
    async def disable_extension(self, ctx, extension_name: str):
        """Disables an extension for the guild.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_name (str): the extension subname to disable
        """
        if not (
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}" in self.bot.extensions
            or f"{self.bot.FUNCTIONS_DIR_NAME}.{extension_name}" in self.bot.extensions
        ):
            await auxiliary.send_deny_embed(
                message="I could not find that extension, or it's not loaded",
                channel=ctx.channel,
            )
            return

        config = self.bot.guild_configs[str(ctx.guild.id)]
        if not extension_name in config.enabled_extensions:
            await auxiliary.send_deny_embed(
                message="That extension is already disabled for this guild",
                channel=ctx.channel,
            )
            return

        config.enabled_extensions = [
            extension
            for extension in config.enabled_extensions
            if extension != extension_name
        ]

        # Modify the database
        await self.bot.write_new_config(str(ctx.guild.id), json.dumps(config))

        # Modify the local cache
        self.bot.guild_configs[str(ctx.guild.id)] = config

        await auxiliary.send_confirm_embed(
            message="I've disabled that extension for this guild", channel=ctx.channel
        )

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @config_command.command(
        name="reset",
        brief="Resets current guild config",
        description="Resets config to default for the current guild",
    )
    async def reset_config(self, ctx: commands.Context):
        """A function to reset the current guild config to stock

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        view = ui.Confirm()
        await view.send(
            message=f"Are you sure you want to reset the config for {ctx.guild.name}?",
            channel=ctx.channel,
            author=ctx.author,
        )
        await view.wait()
        if view.value == ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                message="The config was not reset",
                channel=ctx.channel,
            )
            return
        if view.value == ui.ConfirmResponse.TIMEOUT:
            return

        # Modify the database
        await self.bot.write_new_config(str(ctx.guild.id), "false")

        # Modify the local cache
        self.bot.guild_configs[str(ctx.guild.id)] = False
        await self.bot.create_new_context_config(lookup=str(ctx.guild.id))
        await auxiliary.send_confirm_embed(
            message="I've reset the config for this guild", channel=ctx.channel
        )
