"""Module for custom help commands."""

from dataclasses import dataclass
from itertools import product

import discord
import ui
from core import auxiliary, cogs
from discord import app_commands
from discord.ext import commands


@dataclass
class PrintableCommand:
    """A custom class to store formatted information about a command
    With a priority on being sortable and searchable
    """

    prefix: str
    name: str
    usage: str
    description: str


async def setup(bot):
    """Registers the Helper Cog"""
    await bot.add_cog(Helper(bot=bot))


class Helper(cogs.BaseCog):
    """Cog object for help commands."""

    EXTENSIONS_PER_GENERAL_PAGE = 15

    @commands.command(
        name="help",
        brief="Displays helpful infromation",
        description="Searches commands for your query and dispays usage info",
        usage="[search]",
    )
    async def help_command(self, ctx: commands.Context, search_term: str = "") -> None:
        """Main comand interface for getting help with bot commands.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (commands.Context): the context object for the message
            search_term (str) [Optional]; The term to search command name and descriptions for.
                Will default to empty string
        """
        # Build raw lists of commands
        prefix_command_list = list(self.bot.walk_commands())
        app_command_list = list(self.bot.tree.walk_commands())

        command_prefix = await self.bot.get_prefix(ctx.message)

        # Build a list of custom command objects from the lists
        # Will include aliases and full command names
        all_command_list: list[PrintableCommand] = []

        # Looping through all the prefix commands
        for command in prefix_command_list:
            # If the command is a group, ignore it
            if issubclass(command.__class__, commands.Group):
                continue

            # Check if extension is enabled
            extension_name = self.bot.get_command_extension_name(command)
            config = self.bot.guild_configs[str(ctx.guild.id)]
            if extension_name not in config.enabled_extensions:
                continue

            # Deal with aliases by looping through all parent groups and alises
            # Then, make all permutations and get a string
            # of all full command names (parents alias)
            all_lists = []
            # Loop through all parents
            for parent in command.parents:
                all_lists.append(parent.aliases + [parent.name])

            # Since discord.py makes the parents array opposite of how you would call, reverse
            all_lists.reverse()
            all_lists.append(command.aliases + [command.name])

            # Use itertools to get all permutations
            all_permutations = list(product(*all_lists))
            all_commands = [" ".join(map(str, perm)) for perm in all_permutations]

            # Add all possible permutations to the help menu
            for command_name in all_commands:
                all_command_list.append(
                    PrintableCommand(
                        prefix=command_prefix,
                        name=command_name,
                        usage=command.usage if command.usage else "",
                        description=command.description,
                    )
                )

        # Loop through all the slash commands
        for command in app_command_list:
            # Ignore the command in a group
            if issubclass(command.__class__, app_commands.Group):
                continue

            # Check if extension is enabled
            extension_name = command.extras["module"]
            config = self.bot.guild_configs[str(ctx.guild.id)]
            if extension_name not in config.enabled_extensions:
                continue

            # We have to manually build a string representation of the usage
            # We are given it in a list
            command_usage = ""
            for param in command.parameters:
                command_usage += f"[{param.name}] "

            # Append the app commands.
            # App commands cannot have aliases, so no need to think about that
            all_command_list.append(
                PrintableCommand(
                    prefix="/",
                    name=command.qualified_name,
                    usage=command_usage.strip(),
                    description=command.description,
                )
            )

        # Deal with special modmail commands, if this is the modmail guild
        if self.bot.file_config.modmail_config.enable_modmail and ctx.guild.id == int(
            self.bot.file_config.modmail_config.modmail_guild
        ):
            modmail_cog = ctx.bot.get_cog("Modmail")
            if modmail_cog:
                modmail_commands = modmail_cog.modmail_commands_list()
                for command in modmail_commands:
                    all_command_list.append(
                        PrintableCommand(
                            prefix=command[0],
                            name=command[1],
                            usage=command[2].strip(),
                            description=f"Modmail only: {command[3]}",
                        )
                    )

        # Sort and search the commands
        sorted_commands = sorted(all_command_list, key=lambda x: x.name.lower())
        filtered_commands = [
            command
            for command in sorted_commands
            if search_term.lower() in command.name.lower()
            or search_term.lower() in command.description.lower()
        ]

        # Ensure at least a single command was found
        if not filtered_commands:
            await auxiliary.send_deny_embed(
                message=f"No commands matching `{search_term}` have been found",
                channel=ctx.channel,
            )
            return

        # Use pages to ensure we don't overflow the max embed size
        embeds = self.build_embeds_from_list(filtered_commands, search_term)
        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)

    def build_embeds_from_list(
        self, commands_list: list[PrintableCommand], search_term: str
    ) -> list[discord.Embed]:
        """Takes a list of commands and returns a list of embeds ready to be paginated

        Args:
            commands_list (list[PrintableCommand]): A list of the dataclass PrintableCommand
            search_term (str): The string for the search term.

        Returns:
            list[discord.Embed]: The list of embeds always of at least size 1 ready
                to be shown to the user
        """
        title = f"Commands matching `{search_term}`" if search_term else "All commands"
        sublists: list[list[PrintableCommand]] = [
            commands_list[i : i + 10] for i in range(0, len(commands_list), 10)
        ]
        final_embeds: list[discord.Embed] = []
        for command_list in sublists:
            embed = discord.Embed(title=title, color=discord.Color.green())
            for command in command_list:
                embed.add_field(
                    name=f"{command.prefix}{command.name} {command.usage}",
                    value=command.description,
                    inline=False,
                )
            final_embeds.append(embed)
        return final_embeds
