"""Module for the ipinfo extension into the bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the IP Info plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(IPInfo(bot=bot))


class IPInfo(cogs.BaseCog):
    """Class to add ipinfo geodata to the bot.

    Attrs:
        API_URL (str): The API url for IP info
        IP_ICON_URL (str): The URL for the IP info icon
    """

    API_URL = "https://ipinfo.io"
    IP_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/1858/PNG/512/"
        "iconfinder-dedicatedipaddress-4263513_117864.png"
    )

    @commands.command(
        name="ipinfo",
        aliases=["ip"],
        brief="Gets IP info",
        description="Gets IP info (geodata) from a given IP",
    )
    async def get_info(self: Self, ctx: commands.Context, ip_address: str) -> None:
        """Entry point and main logic for the IP info command

        Args:
            ctx (commands.Context): The context in which the commmand was run in
            ip_address (str): The user inputted IP address to lookup
        """
        response = await self.bot.http_functions.http_call(
            "get", f"{self.API_URL}/{ip_address}/json"
        )

        if not response.get("ip"):
            await auxiliary.send_deny_embed(
                message="I couldn't find that IP", channel=ctx.channel
            )
            return

        response.pop("readme", None)
        response.pop("status_code", None)

        embed = self.generate_embed(ip_address, response)
        await ctx.send(embed=embed)

    def generate_embed(self: Self, ip: str, fields: dict[str, str]) -> discord.Embed:
        """Generates an embed from a set of key, values.

        Args:
            ip (str): the ip address
            fields (dict[str, str]): dictionary containing embed field titles and
                their contents

        Returns:
            discord.Embed: The formatted embed ready to be sent to the user
        """
        embed = discord.Embed(title=f"IP info for {ip}")
        embed.set_thumbnail(url=self.IP_ICON_URL)
        embed.color = discord.Color.dark_green()
        for key, value in fields.items():
            embed.add_field(name=key, value=value, inline=True)
        return embed
