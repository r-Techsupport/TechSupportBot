"""
Module for the emoji command on the discord bot.
This module has unit tests
This modules requires no config, no databases, and no APIs
"""

from unicodedata import lookup

import base
import discord
import emoji
import inflect
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add emoji commands to config."""
    await bot.add_cog(Emojis(bot=bot))


class Emojis(base.BaseCog):
    """Class for all the emoji commands"""

    KEY_MAP = {"?": "question", "!": "exclamation"}

    @classmethod
    def emoji_from_char(cls, char):
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

    def check_if_all_unique(self, string: str):
        """Checks, using the set function, if a string has duplicates or not

        Args:
            string (str): The raw input message

        Returns:
            bool: True if there are no duplicates
        """
        return len(set(string.lower())) == len(string.lower())

    @classmethod
    def generate_emoji_string(cls, string, as_list=False):
        """This takes a string and returns a string or list of emojis

        Args:
            string (str): The raw string to convert to emoji
            as_list (bool, optional): Whether to return a string or list. If true, this returns a list of
                only the unicode without spaces. Defaults to False.

        Returns:
            str/List: The string or list of emojis
        """
        emoji_list = []
        emoji_string = ""

        for char in string:
            if char == " ":
                emoji_string += " "
                continue

            emoji_ = cls.emoji_from_char(char)
            if emoji_:
                emoji_list.append(emoji_)
                emoji_string += emoji_ + " "
            else:
                emoji_string += char + " "

        return emoji_list if as_list else emoji_string

    async def emoji_message_command(self, ctx, message: str) -> None:
        """This handles the core of the message command

        Args:
            ctx (commands.Context): The context in which the message command was run
            message (str): The raw message from discord
        """
        emoji_message = self.generate_emoji_string(string=message, as_list=False)
        if not emoji_message:
            await ctx.send_deny_embed(
                "I can't get any emoji letters from your message!"
            )
            return

        await ctx.send_confirm_embed(emoji_message)

    async def emoji_reaction_command(
        self, ctx, message: str, react_user: discord.Member
    ) -> None:
        """This handles the core of the reaction command

        Args:
            ctx (command.Context): The context in which the reaction command was run
            message (str): The raw message to turn into reactions
            react_user (discord.Member): The member to find the most recent message ot react to
        """
        prefix = await self.bot.get_prefix(ctx.message)

        react_message = await auxiliary.search_channel_for_message(
            channel=ctx.channel, prefix=prefix, member_to_match=react_user
        )
        if not react_message:
            await ctx.send_deny_embed("No valid messages found to react to!")
            return

        if not self.check_if_all_unique(message):
            await ctx.send_deny_embed(
                "Invalid message! Make sure there are no repeat characters!"
            )
            return

        emoji_list = self.generate_emoji_string(string=message, as_list=True)

        if len(emoji_list) == 0:
            await ctx.send_deny_embed(
                "I can't get any emoji letters from your message!"
            )
            return

        await auxiliary.add_list_of_reactions(
            message=react_message, reactions=emoji_list
        )

    @commands.group(
        brief="Executes an emoji command",
        description="Executes a emoji command",
    )
    async def emoji(self, ctx):
        """Executed if there are no/invalid args supplied"""
        await base.extension_help(self, ctx, self.__module__[11:])

    @util.with_typing
    @emoji.command(
        aliases=["msg"],
        brief="Generates an emoji message",
        description="Creates a regional_indiciator_X emoji message",
        usage="[message]",
    )
    async def message(self, ctx, *, message: str):
        """This is a command and should be run via discord
        This is for generating a message of emojis"""
        await self.emoji_message_command(ctx, message)

    @commands.has_permissions(add_reactions=True)
    @commands.guild_only()
    @emoji.command(
        brief="Reacts with emojis",
        description="Creates a regional_indiciator_X emoji reaction for a user's most recent message",
        usage="[message] @user",
    )
    async def reaction(self, ctx, message: str, react_user: discord.Member):
        """This is a command and should be run via discord
        This is for reacting to a message with emojis
        The message must be unique in this command"""
        await self.emoji_reaction_command(ctx, message, react_user)
