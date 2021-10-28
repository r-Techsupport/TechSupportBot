"""Module for custom help commands.
"""

import base
import discord
from discord.ext import commands


class Helper(base.BaseCog):
    """Cog object for help commands."""

    PLUGINS_PER_GENERAL_PAGE = 10

    @commands.command(name="help")
    async def help_command(self, ctx, plugin_name: str = None):
        """Main comand interface for getting help with bot commands.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            plugin_name (str): the plugin name to get help with
        """
        if plugin_name:
            embed = await self.generate_plugin_embed(ctx, plugin_name)
            await ctx.send(embed=embed)
        else:
            embeds = await self.generate_general_embeds(ctx)
            await self.bot.paginate(ctx, embeds)

    async def generate_general_embeds(self, ctx):
        """Generates paginated embeds for the bot's loaded plugins.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        plugin_names = list(self.bot.plugin_api.plugins.keys())
        plugin_names.sort()

        embeds = []
        plugin_name_chunks = self.chunks(plugin_names, self.PLUGINS_PER_GENERAL_PAGE)
        for chunk in plugin_name_chunks:
            embed = await self.generate_general_embed(ctx, chunk)
            embeds.append(embed)

        return embeds

    async def generate_general_embed(self, ctx, plugin_names):
        """Generates a single embed for a list of plugin names.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            plugin_names (List[str]): the plugin names to use
        """
        plugin_name_text = ""
        for plugin_name in plugin_names:
            plugin_name_text += f"- `{plugin_name}`\n"

        # pylint: disable=no-member
        command_prefix = await self.bot.get_prefix(ctx.message)
        embed = discord.Embed(
            title=f"use `{command_prefix}{self.help_command.name} <plugin_name>` to see commands",
            description=plugin_name_text,
        )
        embed.color = discord.Color.green()

        return embed

    async def generate_plugin_embed(self, ctx, plugin_name):
        """Generates a single embed for a given plugin.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            plugin_name (str): the plugin name to get help with
        """
        embed = discord.Embed(title=f"Help - `{plugin_name}`")

        plugin_data = self.bot.plugin_api.plugins.get(plugin_name)
        if not plugin_data:
            embed.description = "That plugin could not be found"
            return embed

        command_prefix = await self.bot.get_prefix(ctx.message)

        commands_found = False
        for cog_name in plugin_data.cogs:
            cog = self.bot.get_cog(cog_name)
            for command in cog.walk_commands():
                if issubclass(command.__class__, commands.Group):
                    continue

                commands_found = True
                if command.full_parent_name == "":
                    syntax = f"{command_prefix}{command.name}"
                else:
                    syntax = (
                        f"{command_prefix}{command.full_parent_name} {command.name}"
                    )

                usage = command.usage or ""

                embed.add_field(
                    name=f"`{syntax} {usage}`", value=command.description, inline=False
                )

        embed.color = discord.Color.green()

        if not commands_found:
            embed.description = "There are no commands for this plugin"
            embed.color = discord.Color.red()

        return embed

    @staticmethod
    def chunks(input_list, size):
        """Return chunks of an input list.

        parameters:
            input_list (list): the list to split up
            size (int): the size of each nested list
        """
        chunks = []
        for ind in range(0, len(input_list), size):
            chunks.append(input_list[ind : ind + size])

        return chunks
