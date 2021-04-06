"""Cog for interfacing with guild configs.
"""

import datetime
import io
import json

import base
import discord
from discord.ext import commands


class ConfigControl(base.BaseCog):
    """Cog object for per-guild config control"""

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.group(
        name="config",
        brief="Executes a config bot command",
        description="Executes a plugin bot command",
    )
    async def config_group(self, ctx):
        # pylint: disable=missing-function-docstring
        pass

    @config_group.command(name="main")
    async def main(self, ctx):
        """Displays the current config to the user.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        config = await self.bot.get_context_config(ctx, get_from_cache=True)

        uploaded_data = await self.bot.get_json_from_attachment(
            ctx.message, allow_failure=False
        )
        if uploaded_data:
            # handle upload instead
            if any(key not in config for key in uploaded_data.keys()):
                await self.bot.tagged_response(
                    ctx,
                    "I couldn't match your upload data with the guild config schema",
                )
                return

            uploaded_data["plugins"] = config.plugins

            await self.bot.guild_config_collection.replace_one(
                {"_id": config.get("_id")}, uploaded_data
            )

            await self.bot.tagged_response(ctx, "I've updated that config")
            return

        plugins_with_config = filter(
            lambda plugin_name: bool(config.plugins.get(plugin_name)),
            config.plugins.keys(),
        )

        json_file = self.convert_config_to_json_file(ctx, config)

        await ctx.send(file=json_file)

    @config_group.command(name="plugin")
    async def plugin(self, ctx, plugin_name: str):
        """Displays the current plugin config to the user.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """

        config = await self.bot.get_context_config(ctx, get_from_cache=True)

        plugin_config = config.plugins.get(plugin_name)
        if not plugin_config:
            await self.bot.tagged_response(
                ctx, "I couldn't find any config for that plugin name"
            )
            return

        uploaded_data = await self.bot.get_json_from_attachment(
            ctx.message, allow_failure=False
        )
        if uploaded_data:
            # handle upload instead
            if any(key not in plugin_config for key in uploaded_data.keys()) or len(
                plugin_config
            ) != len(uploaded_data):
                await self.bot.tagged_response(
                    ctx,
                    "I couldn't match your upload data with the plugin config schema",
                )
                return

            plugin_config = uploaded_data
            config.plugins[plugin_name] = plugin_config

            await self.bot.guild_config_collection.replace_one(
                {"_id": config.get("_id")}, config
            )

            await self.bot.tagged_response(ctx, "I've updated that plugin config")
            return

        json_file = self.convert_config_to_json_file(
            ctx, plugin_config, plugin_name=plugin_name
        )

        await ctx.send(file=json_file)

    def convert_config_to_json_file(self, ctx, config_object, plugin_name=None):
        """Gets a JSON file object from a config object.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            config_object (dict): the config object to serialize
            plugin_name (string): the name of the plugin for the config (if applicable)
        """
        json_config = config_object.copy()

        _id = json_config.get("_id")
        if _id:
            json_config["_id"] = str(_id)

        json_file = discord.File(
            io.StringIO(json.dumps(json_config, indent=4)),
            filename=f"{plugin_name or ctx.guild.name}-config-{datetime.datetime.utcnow()}.json",
        )

        return json_file
