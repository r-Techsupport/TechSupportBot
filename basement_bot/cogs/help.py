"""Module for custom help commands.
"""

import base
import discord
import util
from discord.ext import commands


class Helper(base.BaseCog):
    """Cog object for help commands."""

    PLUGINS_PER_GENERAL_PAGE = 20
    EMBED_COLOR = discord.Color.green()

    @commands.group(name="help")
    async def help_command(self, ctx):
        """Main comand interface for getting help with bot commands.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        if ctx.invoked_subcommand:
            return

        command_prefix = await self.bot.get_prefix(ctx.message)

        embed = discord.Embed(title="Choose commands to get help with")
        help_command_name = getattr(self.help_command, "name")
        embed.add_field(
            name="Builtin commands",
            value=f"`{command_prefix}{help_command_name} builtin`",
            inline=False,
        )
        embed.add_field(
            name="Plugin commands",
            value=f"`{command_prefix}{help_command_name} plugin`",
            inline=False,
        )
        embed.color = self.EMBED_COLOR

        await util.send_with_mention(ctx, embed=embed)

    @help_command.command(name="builtin")
    async def builtin_help_command(self, ctx):
        """Command interface for help with builtin commands.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        command_prefix = await self.bot.get_prefix(ctx.message)

        embed = discord.Embed(title="Builtin commands")
        for cog_name in self.bot.builtin_cogs:
            cog = self.bot.get_cog(cog_name)
            if not cog:
                continue
            embed = self.add_command_fields(cog, embed, command_prefix)

        embed.color = self.EMBED_COLOR

        await util.send_with_mention(ctx, embed=embed)

    @help_command.command(name="plugin")
    async def plugin_help_command(self, ctx, plugin_name: str = None):
        """Command interface for help with plugin commands.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            plugin_name (str): the plugin name to get help with
        """
        if plugin_name:
            embed = await self.generate_plugin_embed(ctx, plugin_name)
            await util.send_with_mention(ctx, embed=embed)
        else:
            embeds = await self.generate_general_embeds(ctx)
            await self.bot.paginate(ctx, embeds)

    async def generate_general_embeds(self, ctx):
        """Generates paginated embeds for the bot's loaded plugins.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        plugin_names = list(self.bot.plugins.keys())
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
            title=f"Use `{command_prefix}{self.help_command.name} {self.plugin_help_command.name} <plugin_name>` to see plugin commands",
            description=plugin_name_text,
        )
        embed.color = self.EMBED_COLOR

        return embed

    async def generate_plugin_embed(self, ctx, plugin_name):
        """Generates a single embed for a given plugin.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            plugin_name (str): the plugin name to get help with
        """
        embed = discord.Embed(title=f"Plugin Commands - `{plugin_name}`")

        plugin_data = self.bot.plugins.get(plugin_name)
        if not plugin_data:
            embed.description = "That plugin could not be found"
            return embed

        command_prefix = await self.bot.get_prefix(ctx.message)

        for cog_name in plugin_data.cogs:
            cog = self.bot.get_cog(cog_name)
            embed = self.add_command_fields(cog, embed, command_prefix)

        embed.color = self.EMBED_COLOR

        if len(embed.fields) == 0:
            embed.description = "There are no commands for this plugin"
            embed.color = discord.Color.red()

        return embed

    @staticmethod
    def add_command_fields(cog, embed, command_prefix):
        """Adds embed fields for each command in a given cog.

        parameters:
            cog (discord.commands.ext.Cog): the cog to reference
            embed (discord.Embed): the embed to add fields to
            command_prefix (str): the command prefix for the bot
        """
        for command in cog.walk_commands():
            if issubclass(command.__class__, commands.Group):
                continue

            if command.full_parent_name == "":
                syntax = f"{command_prefix}{command.name}"
            else:
                syntax = f"{command_prefix}{command.full_parent_name} {command.name}"

            usage = command.usage or ""

            embed.add_field(
                name=f"`{syntax} {usage}`",
                value=command.description or "No description available",
                inline=False,
            )

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
