"""Module for the mock extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Mock plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Mocker(bot=bot))


class Mocker(cogs.BaseCog):
    """Class to set up the mocking command."""

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.command(
        aliases=["sb"],
        brief="Mocks a user",
        description="Mocks the most recent message by a user",
        usage="@user",
    )
    async def mock(
        self: Self, ctx: commands.Context, input_user: discord.Member
    ) -> None:
        """Defines the .mock command on discord

        Args:
            ctx (commands.Context): The context in which the command was run
            input_user (discord.Member): The raw member input by the invoker
        """
        await self.mock_command(ctx, input_user)

    async def mock_command(
        self: Self, ctx: commands.Context, input_user: discord.Member
    ) -> None:
        """The core logic for the mock command

        Args:
            ctx (commands.Context): The context in which the command was run
            input_user (discord.Member): The raw member input by the invoker
        """
        user_to_mock = self.get_user_to_mock(ctx, input_user)

        prefix = await self.bot.get_prefix(ctx.message)
        mock_message = await self.generate_mock_message(
            channel=ctx.channel, user=user_to_mock, prefix=prefix
        )

        if not mock_message:
            await auxiliary.send_deny_embed(
                message=f"No message found for user {user_to_mock}", channel=ctx.channel
            )
            return

        embed = auxiliary.generate_basic_embed(
            title=f'"{mock_message}"',
            description=user_to_mock.name,
            color=discord.Color.greyple(),
            url=user_to_mock.display_avatar.url,
        )

        await ctx.send(embed=embed)

    async def generate_mock_message(
        self: Self, channel: discord.abc.Messageable, user: discord.Member, prefix: str
    ) -> str:
        """Finds a message and converts it into a mock format

        Args:
            channel (discord.abc.Messageable): The channel the mock command was run in
            user (discord.Member): The user to mock
            prefix (str): The current prefix of the bot

        Returns:
            str: The string containing the mocked contents of the message.
                Will be None if no message could be found
        """
        message = await auxiliary.search_channel_for_message(
            channel=channel, prefix=prefix, member_to_match=user
        )

        if not message:
            return None

        return self.prepare_mock_message(message.clean_content)

    def get_user_to_mock(
        self: Self, ctx: commands.Context, input_user: discord.Member
    ) -> discord.Member:
        """Makes sure that the user is to mock is correct..
        This disallows mocking bots and instead makes it mock the invoker

        Args:
            ctx (commands.Context): The context in which the command was run
            input_user (discord.Member): The raw member input by the invoker

        Returns:
            discord.Member: The member to actually be mocked
        """
        if input_user.bot:
            return ctx.author
        return input_user

    def prepare_mock_message(self: Self, message: str) -> str:
        """This turns a string into a uppercase lowercase alternating string

        Args:
            message (str): The contents of a message to convert

        Returns:
            str: The converted string
        """
        mock = ""
        i = True
        for char in message:
            if i:
                mock += char.upper()
            else:
                mock += char.lower()
            if char != " ":
                i = not i
        return mock
