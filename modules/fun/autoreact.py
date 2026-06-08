"""Module for the autoreact extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from discord.ext import commands

import configuration
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Autoreact plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(AutoReact(bot=bot))


class AutoReact(cogs.MatchCog):
    """Class for the autoreact to make it to discord."""

    async def match(self: Self, ctx: commands.Context, content: str) -> bool:
        """A match function to determine if somehting should be reacted to

        Args:
            ctx (commands.Context): The context in which the message was sent
            content (str): The string content of the message

        Returns:
            bool: True if there needs to be a reaction, False otherwise
        """
        search_content = f" {content} "
        search_content = search_content.lower()
        for word in configuration.get_config_entry(ctx.guild.id, "autoreact_react_map"):
            if f" {word.lower()} " in search_content:
                return True
        return False

    async def response(
        self: Self, ctx: commands.Context, content: str, _: bool
    ) -> None:
        """The function to generate and add reactions

        Args:
            ctx (commands.Context): The context in which the message was sent in
            content (str): The string content of the message
        """
        search_content = f" {content} "
        search_content = search_content.lower()
        reactions = []
        reaction_map = configuration.get_config_entry(
            ctx.guild.id, "autoreact_react_map"
        )
        for word in reaction_map:
            if f" {word.lower()} " in search_content:
                reaction = reaction_map.get(word)
                if reaction not in reactions:
                    reactions.append(reaction_map.get(word))
        await auxiliary.add_list_of_reactions(message=ctx.message, reactions=reactions)
