"""Module for the mock extension for the discord bot."""
import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Adding mock config to the config file"""
    await bot.add_cog(Mocker(bot=bot))


class Mocker(base.BaseCog):
    """Class to set up the mocking command."""

    @util.with_typing
    @commands.guild_only()
    @commands.command(
        aliases=["sb"],
        brief="Mocks a user",
        description="Mocks the most recent message by a user",
        usage="@user",
    )
    async def mock(self, ctx: commands.Context, input_user: discord.Member):
        """Defines the .mock command on discord

        Args:
            ctx (commands.Context): The context in which the command was run
            input_user (discord.Member): The raw member input by the invoker
        """
        await self.mock_command(ctx, input_user)

    async def mock_command(self, ctx: commands.Context, input_user: discord.Member):
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
        self, channel: discord.abc.Messageable, user: discord.Member, prefix: str
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
        self, ctx: commands.Context, input_user: discord.Member
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

    def prepare_mock_message(self, message: str) -> str:
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
