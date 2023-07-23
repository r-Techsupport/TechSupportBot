"""Module for config commands.
"""

import datetime
import io
import json

import base
import discord
import ui
import util
from base import auxiliary
from discord.ext import commands


class ConfigControl(base.BaseCog):
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
        config = await self.bot.get_context_config(ctx, get_from_cache=False)

        uploaded_data = await util.get_json_from_attachments(ctx.message)
        if uploaded_data:
            # server-side check of guild
            uploaded_data["guild_id"] = str(ctx.guild.id)
            config_difference = util.config_schema_matches(uploaded_data, config)
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

            await self.bot.guild_config_collection.replace_one(
                {"guild_id": config.get("guild_id")}, uploaded_data
            )

            # Delete config from cache
            if str(ctx.guild.id) in self.bot.guild_config_cache:
                del self.bot.guild_config_cache[str(ctx.guild.id)]

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
        if not self.bot.extensions.get(
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
        ):
            await auxiliary.send_deny_embed(
                message="I could not find that extension, or it's not loaded",
                channel=ctx.channel,
            )
            return

        config = await self.bot.get_context_config(ctx, get_from_cache=False)
        if extension_name in config.enabled_extensions:
            await auxiliary.send_deny_embed(
                message="That extension is already enabled for this guild",
                channel=ctx.channel,
            )
            return

        config.enabled_extensions.append(extension_name)
        config.enabled_extensions.sort()

        await self.bot.guild_config_collection.replace_one(
            {"guild_id": config.get("guild_id")}, config
        )

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
        if not self.bot.extensions.get(
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
        ):
            await auxiliary.send_deny_embed(
                message="I could not find that extension, or it's not loaded",
                channel=ctx.channel,
            )
            return

        config = await self.bot.get_context_config(ctx, get_from_cache=False)
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

        await self.bot.guild_config_collection.replace_one(
            {"guild_id": config.get("guild_id")}, config
        )

        await auxiliary.send_confirm_embed(
            message="I've disabled that extension for this guild", channel=ctx.channel
        )
