"""Module for custom help commands.
"""

from dataclasses import dataclass

import discord
import ui
from base import auxiliary, cogs
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


class Helper(cogs.BaseCog):
    """Cog object for help commands."""

    EXTENSIONS_PER_GENERAL_PAGE = 15

    @commands.group(name="help")
    async def help_command(self, ctx: commands.Context, search_term: str) -> None:
        """Main comand interface for getting help with bot commands.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (commands.Context): the context object for the message
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

            # Append the base command to the list
            all_command_list.append(
                PrintableCommand(
                    prefix=command_prefix,
                    name=command.qualified_name,
                    usage=command.usage if command.usage else "",
                    description=command.description,
                )
            )

            # Prefix commands can have aliases, so make sure we append those as well
            parent_name = f"{command.full_parent_name} "
            for alias in command.aliases:
                all_command_list.append(
                    PrintableCommand(
                        prefix=command_prefix,
                        name=f"{parent_name.lstrip()}{alias.lstrip()}",
                        usage=command.usage if command.usage else "",
                        description=command.description,
                    )
                )

        # Loop through all the slash commands
        for command in app_command_list:
            # Ignore the command in a group
            if issubclass(command.__class__, app_commands.Group):
                continue

            # We have to manually build a string representation of the usage
            # We are given it in a list
            command_usage = ""
            for param in command.parameters:
                command_usage += f"[{param.name}] "

            # Append the app commands.
            # App commands cannot have aliases, so no need to thin about that
            all_command_list.append(
                PrintableCommand(
                    prefix="/",
                    name=command.qualified_name,
                    usage=command_usage.strip(),
                    description=command.description,
                )
            )

        # Sort and search the commands
        sorted_commands = sorted(all_command_list, key=lambda x: x.name)
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
            search_term (str): The string for the search term

        Returns:
            list[discord.Embed]: The list of embeds always of at least size 1 ready
                to be shown to the user
        """
        sublists: list[list[PrintableCommand]] = [
            commands_list[i : i + 10] for i in range(0, len(commands_list), 10)
        ]
        final_embeds: list[discord.Embed] = []
        for command_list in sublists:
            embed = discord.Embed(
                title=f"Commands matching `{search_term}`", color=discord.Color.green()
            )
            for command in command_list:
                embed.add_field(
                    name=f"{command.prefix}{command.name} {command.usage}",
                    value=command.description,
                    inline=False,
                )
            final_embeds.append(embed)
        return final_embeds
