"""Module for the ipinfo extension into the bot."""

import discord
from core import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Method to add ipinfo to the config file."""
    await bot.add_cog(IPInfo(bot=bot))


class IPInfo(cogs.BaseCog):
    """Class to add ipinfo geodata to the bot."""

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
    async def get_info(self, ctx, ip_address: str):
        """Method to get the info for the ipinfo command for the bot."""
        response = await self.bot.http_functions.http_call(
            method="get", url=f"{self.API_URL}/{ip_address}/json"
        )

        if not response.get("ip"):
            await auxiliary.send_deny_embed(
                message="I couldn't find that IP", channel=ctx.channel
            )
            return

        response.pop("readme", None)
        response.pop("status_code", None)

        embed = self.generate_embed(ip=ip_address, fields=response)
        await ctx.send(embed=embed)

    def generate_embed(self, ip: str, fields: dict[str, str]) -> discord.Embed:
        """Generates an embed from a set of key, values.

        Args:
            ip (str): the ip address
            fields (dict): dictionary containing embed field titles and
            their contents
        """
        embed = discord.Embed(title=f"IP info for {ip}")
        embed.set_thumbnail(url=self.IP_ICON_URL)
        embed.color = discord.Color.dark_green()
        for key, value in fields.items():
            embed.add_field(name=key, value=value, inline=True)
        return embed
