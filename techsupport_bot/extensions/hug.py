"""Module for the hug extention for the bot."""
import random

import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add hug to the config file."""
    await bot.add_cog(Hugger(bot=bot))


class Hugger(base.BaseCog):
    """Class to make the hug command."""

    HUGS_SELECTION = [
        "{user_giving_hug} hugs {user_to_hug} forever and ever and ever",
        "{user_giving_hug} wraps arms around {user_to_hug} and clings forever",
        "{user_giving_hug} hugs {user_to_hug} and gives their hair a sniff",
        "{user_giving_hug} glomps {user_to_hug}",
        "cant stop, wont stop. {user_giving_hug} hugs {user_to_hug} until the sun goes cold",
        "{user_giving_hug} reluctantly hugs {user_to_hug}...",
        "{user_giving_hug} hugs {user_to_hug} into a coma",
        "{user_giving_hug} smothers {user_to_hug} with a loving hug",
        "{user_giving_hug} squeezes {user_to_hug} to death",
    ]
    ICON_URL = (
        "https://cdn.icon-icons.com/icons2/1648/PNG/512/10022huggingface_110042.png"
    )

    @util.with_typing
    @commands.guild_only()
    @commands.command(
        name="hug",
        brief="Hugs a user",
        description="Hugs a mentioned user using an embed",
        usage="@user",
    )
    async def hug(self, ctx: commands.Context, user_to_hug: discord.Member):
        """The .hug discord command function

        Args:
            ctx (commands.Context): The context in which the command was run in
            user_to_hug (discord.Member): The user to hug
        """
        await self.hug_command(ctx, user_to_hug)

    def check_hug_eligibility(
        self,
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
        self, author: discord.Member, user_to_hug: discord.Member
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
        self, ctx: commands.Context, user_to_hug: discord.Member
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
