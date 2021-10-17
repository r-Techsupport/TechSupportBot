"""Module for config commands.
"""

import datetime
import io
import json

import base
import discord
from discord.ext import commands, ipc


class ConfigControl(base.BaseCog):
    """Cog object for per-guild config control"""

    def schema_matches(self, input_config, current_config):
        """Performs a schema check on an input config.

        parameters:
            input_config (dict): the config to be added
            current_config (dict): the current config
        """
        if (
            any(key not in current_config for key in input_config.keys())
            or len(current_config) != len(input_config) + 1
        ):
            return False

        return True

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @commands.command(
        name="config",
        brief="Edits guild config",
        description="Edits guild config by uploading JSON",
        usage="|uploaded-json|",
    )
    async def config_command(self, ctx):
        """Displays the current config to the user.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        config = await self.bot.get_context_config(ctx, get_from_cache=False)

        uploaded_data = await self.bot.get_json_from_attachments(ctx.message)
        if uploaded_data:
            # server-side check of guild
            uploaded_data["guild_id"] = str(ctx.guild.id)
            if not self.schema_matches(uploaded_data, config):
                await self.bot.send_with_mention(
                    ctx,
                    "I couldn't match your upload data with the current config schema",
                )
                return

            await self.bot.guild_config_collection.replace_one(
                {"guild_id": config.get("guild_id")}, uploaded_data
            )

            await self.bot.send_with_mention(ctx, "I've updated that config")
            return

        json_config = config.copy()

        json_config.pop("_id", None)

        json_file = discord.File(
            io.StringIO(json.dumps(json_config, indent=4)),
            filename=f"{ctx.guild.id}-config-{datetime.datetime.utcnow()}.json",
        )

        await ctx.send(file=json_file)

    @ipc.server.route(name="get_bot_config")
    async def get_bot_config_endpoint(self, _):
        """IPC endpoint for getting bot config."""
        return self.bot.ipc_response(payload=self.bot.config)

    @ipc.server.route(name="get_guild_config")
    async def get_guild_config_endpoint(self, data):
        """IPC endpoint for getting guild config.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return self.bot.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return self.bot.ipc_response(code=404, error="Guild not found")

        config = await self.bot.get_context_config(guild=guild, get_from_cache=True)
        config.pop("_id", None)

        return self.bot.ipc_response(payload=config)

    @ipc.server.route(name="edit_guild_config")
    async def edit_guild_config_endpoint(self, data):
        """IPC endpoint for updating guild config.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return self.bot.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return self.bot.ipc_response(code=404, error="Guild not found")

        current_config = await self.bot.get_context_config(
            guild=guild, get_from_cache=False
        )

        config = getattr(data, "new_config", None)
        if not config:
            return self.bot.ipc_response(code=400, error="Config not provided")

        if not self.schema_matches(config, current_config):
            return self.bot.ipc_response(
                code=400, error="Current config schema doesn't match new config"
            )

        await self.bot.guild_config_collection.replace_one(
            {"guild_id": config.get("guild_id")}, config
        )

        return self.bot.ipc_response()
