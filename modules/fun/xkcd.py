"""Module for the xkcd extension for the discord bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
import munch
from discord import app_commands

from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the XKCD plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(XKCD(bot=bot))


class XKCD(cogs.BaseCog):
    """Class to create the xkcd for the extension.

    Attributes:
        MOST_RECENT_API_URL (str): The URL for the most recent comic
        SPECIFIC_API_URL (str): The URL for a given number comic
        xkcd (app_commands.Group): The group for the /xkcd commands

    """

    MOST_RECENT_API_URL: str = "https://xkcd.com/info.0.json"
    SPECIFIC_API_URL: str = "https://xkcd.com/%s/info.0.json"

    xkcd: app_commands.Group = app_commands.Group(
        name="xkcd", description="Command Group for the XKCD Extension"
    )

    @xkcd.command(
        name="latest",
        description="Gets the latest XKCD comic.",
    )
    async def xkcd_latest(self: Self, interaction: discord.Interaction) -> None:
        """This calls the XKCD API and gets the latest comic

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        await interaction.response.defer()
        latest_comic_data = await self.api_call()
        if latest_comic_data.status_code != 200:
            embed = auxiliary.prepare_deny_embed(
                message="I had trouble looking up XKCD's comics"
            )
            await interaction.followup.send(embed=embed)
            return

        embed = self.generate_embed(latest_comic_data)
        if not embed:
            embed = auxiliary.prepare_deny_embed(
                message="I had trouble calling getting the correct XKCD info",
            )

        await interaction.followup.send(embed=embed)

    @xkcd.command(
        name="random",
        description="Gets a random XKCD comic.",
    )
    async def xkcd_random(self: Self, interaction: discord.Interaction) -> None:
        """This calls the XKCD API and gets a random comic

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        await interaction.response.defer()
        latest_comic_data = await self.api_call()
        if latest_comic_data.status_code != 200:
            embed = auxiliary.prepare_deny_embed(
                message="I had trouble looking up XKCD's comics"
            )
            await interaction.followup.send(embed=embed)
            return

        max_number = latest_comic_data.get("num")
        if not max_number:
            embed = auxiliary.prepare_deny_embed(
                message="I could not determine the max XKCD number"
            )
            await interaction.followup.send(embed=embed)
            return

        comic_number = random.randint(1, max_number)

        random_comic_data = await self.api_call(number=comic_number)
        if random_comic_data.status_code != 200:
            embed = auxiliary.prepare_deny_embed(
                message=f"I had trouble calling a random comic (#{comic_number})",
            )
            await interaction.followup.send(embed=embed)
            return

        embed = self.generate_embed(random_comic_data)
        if not embed:
            embed = auxiliary.prepare_deny_embed(
                message="I had trouble calling getting the correct XKCD info",
            )

        await interaction.followup.send(embed=embed)

    @xkcd.command(
        name="specific",
        description="Gets an XKCD comic by number.",
        extras={"usage": "[comic_number]"},
    )
    async def xkcd_specific(
        self: Self, interaction: discord.Interaction, comic_number: int
    ) -> None:
        """This calls the XKCD API and gets a specific comic

        Args:
            interaction (discord.Interaction): The interaction that called this command
            comic_number (int): The number of the comic to fetch from XKCD
        """
        await interaction.response.defer()

        comic_data = await self.api_call(number=comic_number)
        if comic_data.status_code != 200:
            embed = auxiliary.prepare_deny_embed(
                message=f"I had trouble calling the comic (#{comic_number})",
            )
            await interaction.followup.send(embed=embed)
            return

        embed = self.generate_embed(comic_data)
        if not embed:
            embed = auxiliary.prepare_deny_embed(
                message="I had trouble calling getting the correct XKCD info",
            )

        await interaction.followup.send(embed=embed)

    async def api_call(self: Self, number: int = None) -> munch.Munch:
        """Makes an API call to xkcd to get the json for a given comic

        Args:
            number (int, optional): The comic number to get.
                If none is provided it will use the last comic called by the system.
                Defaults to None.

        Returns:
            munch.Munch: The response from the API
        """
        url = self.SPECIFIC_API_URL % (number) if number else self.MOST_RECENT_API_URL
        response = await self.bot.http_functions.http_call("get", url)

        return response

    def generate_embed(self: Self, comic_data: munch.Munch) -> discord.Embed:
        """Turns a comic json into an embed to be sent to disocrd

        Args:
            comic_data (munch.Munch): The API response containing the comic

        Returns:
            discord.Embed: The formatted embed ready to be sent
        """
        num = comic_data.get("num")
        image_url = comic_data.get("img")
        title = comic_data.get("safe_title")
        alt_text = comic_data.get("alt")

        if not all([num, image_url, title, alt_text]):
            return None

        embed = discord.Embed(title=title, description=f"https://xkcd.com/{num}")
        embed.set_author(name=f"XKCD #{num}")
        embed.set_image(url=image_url)
        embed.set_footer(text=alt_text)
        embed.color = discord.Color.blue()

        return embed
