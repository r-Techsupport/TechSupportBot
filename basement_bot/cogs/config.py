"""Module for config commands.
"""

import datetime
import io
import json

import base
import discord
import util
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
            if not util.config_schema_matches(uploaded_data, config):
                await util.send_deny_embed(
                    ctx,
                    "I couldn't match your upload data with the current config schema",
                )
                return

            await self.bot.guild_config_collection.replace_one(
                {"guild_id": config.get("guild_id")}, uploaded_data
            )

            await util.send_confirm_embed(ctx, "I've updated that config")
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
            await util.send_deny_embed(
                ctx, "I could not find that extension, or it's not loaded"
            )
            return

        config = await self.bot.get_context_config(ctx, get_from_cache=False)
        if extension_name in config.enabled_extensions:
            await util.send_deny_embed(
                ctx, "That extension is already enabled for this guild"
            )
            return

        config.enabled_extensions.append(extension_name)
        config.enabled_extensions.sort()

        await self.bot.guild_config_collection.replace_one(
            {"guild_id": config.get("guild_id")}, config
        )

        await util.send_confirm_embed(ctx, "I've enabled that extension for this guild")

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
            await util.send_deny_embed(
                ctx, "I could not find that extension, or it's not loaded"
            )
            return

        config = await self.bot.get_context_config(ctx, get_from_cache=False)
        if not extension_name in config.enabled_extensions:
            await util.send_deny_embed(
                ctx, "That extension is already disabled for this guild"
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

        await util.send_confirm_embed(
            ctx, "I've disabled that extension for this guild"
        )
