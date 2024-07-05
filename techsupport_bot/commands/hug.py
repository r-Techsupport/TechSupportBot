"""Module for the hug extension for the bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Hug plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Hugger(bot=bot))


class Hugger(cogs.BaseCog):
    """Class to make the hug command.

    Attrs:
        HUGS_SELECTION (list[str]): The list of hug phrases to display
        ICON_URL (str): The icon to use when hugging

    """

    HUGS_SELECTION = [
        "{user_giving_hug} hugs {user_to_hug} forever and ever and ever",
        "{user_giving_hug} wraps arms around {user_to_hug} and clings forever",
        "{user_giving_hug} hugs {user_to_hug} and gives their hair a sniff",
        "{user_giving_hug} glomps {user_to_hug}",
        (
            "cant stop, wont stop. {user_giving_hug} hugs {user_to_hug} until the sun"
            " goes cold"
        ),
        "{user_giving_hug} reluctantly hugs {user_to_hug}...",
        "{user_giving_hug} hugs {user_to_hug} into a coma",
        "{user_giving_hug} smothers {user_to_hug} with a loving hug",
        "{user_giving_hug} squeezes {user_to_hug} to death",
    ]
    ICON_URL = (
        "https://cdn.icon-icons.com/icons2/1648/PNG/512/10022huggingface_110042.png"
    )

    @auxiliary.with_typing
    @commands.guild_only()
    @commands.command(
        name="hug",
        brief="Hugs a user",
        description="Hugs a mentioned user using an embed",
        usage="@user",
    )
    async def hug(
        self: Self, ctx: commands.Context, user_to_hug: discord.Member = None
    ) -> None:
        """The .hug discord command function

        Args:
            ctx (commands.Context): The context in which the command was run in
            user_to_hug (discord.Member): The user to hug
        """
        if user_to_hug is None:
            # check if the message is a reply
            if ctx.message.reference is None:
                await auxiliary.send_deny_embed(
                    message="You need to mention someone to hug", channel=ctx.channel
                )
                return

            user_to_hug = ctx.message.reference.resolved.author

        await self.hug_command(ctx, user_to_hug)

    def check_hug_eligibility(
        self: Self,
        author: discord.Member,
        user_to_hug: discord.Member,
    ) -> bool:
        """Checks to see if the hug is allowed
        Checks to see if the author and target match

        Args:
            author (discord.Member): The author of the hug command
            user_to_hug (discord.Member): The user to hug

        Returns:
            bool: True if the command should proceed, false if it shouldn't
        """
        if user_to_hug == author:
            return False
        return True

    def generate_hug_phrase(
        self: Self, author: discord.Member, user_to_hug: discord.Member
    ) -> str:
        """Generates a hug phrase from the HUGS_SELECTION variable

        Args:
            author (discord.Member): The author of the hug command
            user_to_hug (discord.Member): The user to hug

        Returns:
            str: The filled in hug str
        """
        hug_text = random.choice(self.HUGS_SELECTION).format(
            user_giving_hug=author.mention,
            user_to_hug=user_to_hug.mention,
        )
        return hug_text

    async def hug_command(
        self: Self, ctx: commands.Context, user_to_hug: discord.Member
    ) -> None:
        """The main logic for the hug command

        Args:
            ctx (commands.Context): The context in which the command was run in
            user_to_hug (discord.Member): The user to hug
        """
        if not self.check_hug_eligibility(ctx.author, user_to_hug):
            await auxiliary.send_deny_embed(
                message="Let's be serious", channel=ctx.channel
            )
            return

        hug_text = self.generate_hug_phrase(ctx.author, user_to_hug)

        embed = auxiliary.generate_basic_embed(
            title="You've been hugged!",
            description=hug_text,
            color=discord.Color.blurple(),
            url=self.ICON_URL,
        )

        await ctx.send(
            embed=embed, content=auxiliary.construct_mention_string([user_to_hug])
        )
