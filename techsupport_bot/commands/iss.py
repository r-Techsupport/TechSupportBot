"""Module to add the location of the ISS to the bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the ISS plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(ISSLocator(bot=bot))


class ISSLocator(cogs.BaseCog):
    """Class to locate the ISS at its current position.

    Attrs:
        ISS_URL (str): The API URL to get the location of the ISS
        GEO_URL (str): The API URL to turn lat/lon to location

    """

    ISS_URL = "http://api.open-notify.org/iss-now.json"
    GEO_URL = "https://geocode.xyz/{},{}?geoit=json"

    @auxiliary.with_typing
    @commands.command(
        name="iss",
        brief="Finds the ISS",
        description="Returns the location of the International Space Station (ISS)",
    )
    async def iss(self: Self, ctx: commands.Context) -> None:
        """Entry point and main logic for the iss command
        Will call the API, format and send an embed

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        # get ISS coordinates
        response = await self.bot.http_functions.http_call("get", self.ISS_URL)
        if not response:
            await auxiliary.send_deny_embed(
                message="I had trouble calling the ISS API. Maybe it's down?",
                channel=ctx.channel,
            )
            return
        coordinates = response.get("iss_position", {})
        longitude, latitude = coordinates.get("longitude"), coordinates.get("latitude")
        if not longitude or not latitude:
            await auxiliary.send_deny_embed(
                message="I couldn't find the ISS coordinates from the API response",
                channel=ctx.channel,
            )
            return

        # get location information from coordinates
        location = None
        response = await self.bot.http_functions.http_call(
            "get", self.GEO_URL.format(latitude, longitude)
        )
        if not response:
            await auxiliary.send_deny_embed(
                message="I had trouble calling the GEO API. Maybe it's down?",
                channel=ctx.channel,
            )
        osmtags = response.get("osmtags", {})
        location = osmtags.get("name")

        if not location:
            location = "Unknown"

        embed = discord.Embed(
            title="ISS Location", description="Track the International Space Station!"
        )
        embed.add_field(name="Location", value=location)
        embed.add_field(name="Latitude", value=latitude)
        embed.add_field(name="Longitude", value=longitude)
        embed.add_field(
            name="Real-time tracking",
            value="https://spotthestation.nasa.gov/tracking_map.cfm",
        )
        embed.set_thumbnail(
            url="https://cdn.icon-icons.com/icons2/1389/PNG/512/internationalspacestation_96150.png"
        )
        embed.color = discord.Color.darker_gray()

        await ctx.send(embed=embed)
