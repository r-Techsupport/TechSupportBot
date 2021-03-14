"""Cog for interfacing with guild configs.
"""

import base
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

        plugins_with_config = filter(
            lambda plugin_name: bool(config.plugins.get(plugin_name)),
            config.plugins.keys(),
        )

        embed = self.bot.embed_api.Embed(title=f"Config for {ctx.guild.name}")

        embed.add_field(
            name="Command prefix", value=config.command_prefix, inline=False
        )
        embed.add_field(
            name="Plugins with config",
            value=", ".join(plugins_with_config),
            inline=False,
        )

        embed.set_thumbnail(url=ctx.guild.icon_url)

        await self.bot.tagged_response(ctx, embed=embed)

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

        embeds = []
        for config_entry in plugin_config.values():
            embed = self.bot.embed_api.Embed(
                title=f"{plugin_name}: {config_entry.title}",
                description=config_entry.description,
            )

            embed.add_field(name="Datatype", value=config_entry.datatype)
            embed.add_field(name="Default", value=config_entry.default)
            embed.add_field(name="Value", value=config_entry.value)

            embeds.append(embed)

        self.bot.task_paginate(ctx, embeds)

    @config_group.command(name="prefix")
    async def prefix(self, ctx, prefix: str):
        """Sets the current command prefix for the guild.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            prefix (str): the command prefix to use
        """
        config = await self.bot.get_context_config(ctx, get_from_cache=False)

        if config.command_prefix == prefix:
            await self.bot.tagged_response(
                ctx, "I am already using that command prefix"
            )
            return

        config.command_prefix = prefix

        await self.bot.guild_config_collection.replace_one(
            {"_id": config.get("_id")}, config
        )

        await self.bot.tagged_response(
            ctx, f"I am now using the command prefix: `{config.command_prefix}`"
        )
