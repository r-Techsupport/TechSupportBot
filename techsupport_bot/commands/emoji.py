"""
Module for the emoji command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self
from unicodedata import lookup

import discord
import emoji
import inflect
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Emoji plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Emojis(bot=bot))


class Emojis(cogs.BaseCog):
    """Class for all the emoji commands

    Attrs:
        KEY_MAP (dict[str,str]): Some manual mappings from character to emoji
    """

    KEY_MAP = {"?": "question", "!": "exclamation"}

    @classmethod
    def emoji_from_char(cls: Self, char: str) -> str:
        """Gets an unicode emoji from a character

        Args:
            char (str): The character to look up the emoji from

        Returns:
            str: A string containing the unicode emoji assigned to the character.
                Will not return anything if there is not unicode emoji
        """
        if char.isalpha():
            return lookup(f"REGIONAL INDICATOR SYMBOL LETTER {char.upper()}")
        if char.isnumeric():
            char = inflect.engine().number_to_words(char)
            return emoji.emojize(f":{char}:", language="alias")
        if cls.KEY_MAP.get(char):
            return emoji.emojize(f":{cls.KEY_MAP[char]}:", language="alias")
        return None

    def check_if_all_unique(self: Self, string: str) -> bool:
        """Checks, using the set function, if a string has duplicates or not

        Args:
            string (str): The raw input message

        Returns:
            bool: True if there are no duplicates
        """
        return len(set(string.lower())) == len(string.lower())

    @classmethod
    def generate_emoji_string(
        cls: Self, string: str, only_emoji: bool = False
    ) -> list[str]:
        """This takes a string and returns a string or list of emojis

        Args:
            string (str): The raw string to convert to emoji
            only_emoji (bool, optional): Whether to allow non emoji characters in the list
              Defaults to False.

        Returns:
            list[str]: The string or list of emojis
        """
        emoji_list = []

        for char in string:
            if char == " ":
                continue

            emoji_ = cls.emoji_from_char(char)
            if emoji_:
                emoji_list.append(emoji_)
            elif not only_emoji:
                emoji_list.append(char)

        return emoji_list

    async def emoji_commands(
        self: Self,
        ctx: commands.Context,
        message: str,
        add_reactions: bool,
        react_user: discord.Member = None,
    ) -> None:
        """A method to handle the core of both emoji message and reaction

        Args:
            ctx (commands.Context): The context in which the command was run in
            message (str): The raw message to turn into emojis
            add_reactions (bool): Whether or not to add reactions or send a message
            react_user (discord.Member, optional): The member to react to, if applicable.
                Defaults to None.
        """
        prefix = await self.bot.get_prefix(ctx.message)

        # Basic check to ensure the message isn't nothing
        # Add reactions means everything must be an emoji.
        # So if add reactions is true, only_emoji must be true
        emoji_message = self.generate_emoji_string(
            string=message, only_emoji=add_reactions
        )

        # Ensure there is something to send
        if len(emoji_message) == 0:
            await auxiliary.send_deny_embed(
                message="I can't get any emoji letters from your message!",
                channel=ctx.channel,
            )
            return

        # If a user was passed, get the message to react to
        react_message = None
        if react_user:
            react_message = await auxiliary.search_channel_for_message(
                channel=ctx.channel, prefix=prefix, member_to_match=react_user
            )
            if not react_message:
                await auxiliary.send_deny_embed(
                    message="No valid messages found to react to!", channel=ctx.channel
                )
                return
            if len(react_message.reactions) + len(emoji_message) > 20:
                await auxiliary.send_deny_embed(
                    message="Reaction Count too many", channel=ctx.channel
                )
                return
        # Finally, send the emojis as an embed or a reaction
        if add_reactions:
            if not self.check_if_all_unique(message):
                await auxiliary.send_deny_embed(
                    message=(
                        "Invalid message! Make sure there are no repeat characters!"
                    ),
                    channel=ctx.channel,
                )
                return

            await auxiliary.add_list_of_reactions(
                message=react_message, reactions=emoji_message
            )
        else:
            await auxiliary.send_confirm_embed(
                message=" ".join(emoji_message), channel=ctx.channel
            )

    @commands.group(
        brief="Executes an emoji command",
        description="Executes a emoji command",
    )
    async def emoji(self: Self, ctx: commands.Context) -> None:
        """The bare .emoji command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @emoji.command(
        aliases=["msg"],
        brief="Generates an emoji message",
        description="Creates an emoji message",
        usage="[message]",
    )
    async def message(self: Self, ctx: commands.Context, *, message: str) -> None:
        """Entry point for the message generation emoji command

        Args:
            ctx (commands.Context): The context in which the command was run
            message (str): The string to turn into emojis
        """
        await self.emoji_commands(ctx, message, False)

    @commands.has_permissions(add_reactions=True)
    @commands.guild_only()
    @emoji.command(
        brief="Reacts with emojis",
        description="Creates an emoji reaction for a user's most recent message",
        usage="[message] @user",
    )
    async def reaction(
        self: Self, ctx: commands.Context, message: str, react_user: discord.Member
    ) -> None:
        """Entry point for the reaction emoji command

        Args:
            ctx (commands.Context): The context in which the command was run
            message (str): The string to add as reactions
            react_user (discord.Member): The member whose message is to be reacted to
        """
        await self.emoji_commands(ctx, message, True, react_user)
