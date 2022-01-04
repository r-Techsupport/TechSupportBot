"""Module for custom help commands.
"""

import base
import discord
import util
from discord.ext import commands


class HelpEmbed(discord.Embed):
    """Base embed for admin commands."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.green()


class Helper(base.BaseCog):
    """Cog object for help commands."""

    EXTENSIONS_PER_GENERAL_PAGE = 15

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

        embed = HelpEmbed(title="Choose commands to get help with")
        help_command_name = getattr(self.help_command, "name")
        embed.add_field(
            name="Builtin commands",
            value=f"`{command_prefix}{help_command_name} builtin`",
            inline=False,
        )
        embed.add_field(
            name="extension commands",
            value=f"`{command_prefix}{help_command_name} extension`",
            inline=False,
        )

        await util.send_with_mention(ctx, embed=embed)

    @help_command.command(name="builtin")
    async def builtin_help_command(self, ctx):
        """Command interface for help with builtin commands.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        command_prefix = await self.bot.get_prefix(ctx.message)

        embed = HelpEmbed(title="Builtin commands")
        for cog_name in self.bot.builtin_cogs:
            cog = self.bot.get_cog(cog_name)
            if not cog:
                continue
            embed = self.add_cog_command_fields(cog, embed, command_prefix)

        await util.send_with_mention(ctx, embed=embed)

    @help_command.command(name="extension")
    async def extension_help_command(self, ctx, extension_name: str = None):
        """Command interface for help with extension commands.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_name (str): the extension name to get help with
        """
        if extension_name:
            embed = await self.generate_extension_embed(ctx, extension_name)
            await util.send_with_mention(ctx, embed=embed)
        else:
            embeds = await self.generate_general_embeds(ctx)
            await self.bot.paginate(ctx, embeds)

    def get_extension_names(self):
        """Gets a list of extension names loaded by bot."""
        extension_names = []
        for full_extension_name in self.bot.extensions.keys():
            if not full_extension_name.startswith(f"{self.bot.EXTENSIONS_DIR_NAME}."):
                continue
            extension_names.append(full_extension_name.split(".")[1])

        extension_names.sort()

        return extension_names

    async def generate_general_embeds(self, ctx):
        """Generates paginated embeds for the bot's loaded extensions.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        extension_names = self.get_extension_names()

        embeds = []
        extension_name_chunks = self.chunks(
            extension_names, self.EXTENSIONS_PER_GENERAL_PAGE
        )
        for chunk in extension_name_chunks:
            embed = await self.generate_general_embed(ctx, chunk)
            embeds.append(embed)

        return embeds

    async def generate_general_embed(self, ctx, extension_names):
        """Generates a single embed for a list of extension names.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_names (List[str]): the extension names to use
        """
        extension_name_text = ""
        for extension_name in extension_names:
            extension_name_text += f"- `{extension_name}`\n"

        # pylint: disable=no-member
        command_prefix = await self.bot.get_prefix(ctx.message)
        embed = HelpEmbed(
            title=f"Use `{command_prefix}{self.help_command.name} {self.extension_help_command.name} <extension_name>` to see extension commands",
            description=extension_name_text,
        )

        return embed

    async def generate_extension_embed(self, ctx, extension_name):
        """Generates a single embed for a given extension.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_name (str): the extension name to get help with
        """
        embed = HelpEmbed(title=f"Extension Commands: `{extension_name}`")

        if not self.bot.extensions.get(
            f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
        ):
            embed.description = "That extension could not be found"
            return embed

        command_prefix = await self.bot.get_prefix(ctx.message)

        embed = self.add_extension_command_fields(extension_name, embed, command_prefix)

        if len(embed.fields) == 0:
            embed.description = "There are no commands for this extension"

        return embed

    def add_cog_command_fields(self, cog, embed, command_prefix):
        """Adds embed fields for each command in a given cog.

        parameters:
            extension_name (str): the name of the extension
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

    def add_extension_command_fields(self, extension_name, embed, command_prefix):
        """Adds embed fields for each command in a given cog.

        parameters:
            extension_name (str): the name of the extension
            embed (discord.Embed): the embed to add fields to
            command_prefix (str): the command prefix for the bot
        """
        for command in self.bot.walk_commands():
            command_extension_name = self.bot.get_command_extension_name(command)
            if extension_name != command_extension_name:
                continue

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
