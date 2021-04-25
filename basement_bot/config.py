"""Module for config commands.
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
    @commands.command(
        name="config",
        brief="Edits guild config",
        description="Edits guild config by uploading JSON",
        usage="|uploaded-json|",
    )
    async def config(self, ctx):
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

        json_config = config.copy()

        json_config.pop("_id", None)

        json_file = discord.File(
            io.StringIO(json.dumps(json_config, indent=4)),
            filename=f"{ctx.guild.id}-config-{datetime.datetime.utcnow()}.json",
        )

        await ctx.send(file=json_file)
