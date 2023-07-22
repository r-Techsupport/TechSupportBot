"""Module for the ipinfo extension into the bot."""
import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add ipinfo to the config file."""
    await bot.add_cog(IPInfo(bot=bot))


class IPInfo(base.BaseCog):
    """Class to add ipinfo geodata to the bot."""

    API_URL = "https://ipinfo.io"
    IP_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/1858/PNG/512/"
        "iconfinder-dedicatedipaddress-4263513_117864.png"
    )

    @commands.cooldown(1, 30, commands.BucketType.channel)
    @commands.command(
        name="ipinfo",
        aliases=["ip"],
        brief="Gets IP info",
        description="Gets IP info (geodata) from a given IP",
    )
    async def get_info(self, ctx, ip_address: str):
        """Method to get the info for the ipinfo command for the bot."""
        response = await self.bot.http_call("get", f"{self.API_URL}/{ip_address}/json")

        if not response.get("ip"):
            await auxiliary.send_deny_embed(
                message="I couldn't find that IP", channel=ctx.channel
            )
            return

        response.pop("readme", None)
        response.pop("status_code", None)

        embed = util.generate_embed_from_kwargs(
            title=f"IP info for {ip_address}", all_inline=True, **response
        )

        embed.set_thumbnail(url=self.IP_ICON_URL)
        embed.color = discord.Color.dark_green()

        await ctx.send(embed=embed)
