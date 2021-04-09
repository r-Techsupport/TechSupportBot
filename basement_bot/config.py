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

        uploaded_data = await self.bot.get_json_from_attachments(ctx.message)
        if uploaded_data:
            # server-side check of guild
            uploaded_data["guild_id"] = ctx.guild.id
            if (
                any(key not in config for key in uploaded_data.keys())
                or len(config) != len(uploaded_data) + 1
            ):
                await self.bot.send_with_mention(
                    ctx,
                    "I couldn't match your upload data with the guild config schema",
                )
                return

            await self.bot.guild_config_collection.replace_one(
                {"guild_id": config.get("guild_id")}, uploaded_data
            )

            await self.bot.send_with_mention(ctx, "I've updated that config")
            return

        json_file = self.convert_config_to_json_file(ctx, config)

        await ctx.send(file=json_file)

    def convert_config_to_json_file(self, ctx, config_object, plugin_name=None):
        """Gets a JSON file object from a config object.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            config_object (dict): the config object to serialize
            plugin_name (string): the name of the plugin for the config (if applicable)
        """
        json_config = config_object.copy()

        json_config.pop("_id")

        json_file = discord.File(
            io.StringIO(json.dumps(json_config, indent=4)),
            filename=f"{plugin_name or ctx.guild.name}-config-{datetime.datetime.utcnow()}.json",
        )

        return json_file
