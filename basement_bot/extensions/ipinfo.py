import base
import discord
import util
from discord.ext import commands


def setup(bot):
    bot.add_cog(IPInfo(bot=bot))


class IPInfo(base.BaseCog):

    API_URL = "https://ipinfo.io"
    IP_ICON_URL = "https://cdn.icon-icons.com/icons2/1858/PNG/512/iconfinder-dedicatedipaddress-4263513_117864.png"

    @commands.command(
        name="ipinfo",
        alias=["ip"],
        brief="Gets IP info",
        description="Gets IP info (geodata) from a given IP",
    )
    async def get_info(self, ctx, ip_address: str):
        response = await util.http_call("get", f"{self.API_URL}/{ip_address}/json")

        if not response.get("ip"):
            await util.send_with_mention(ctx, "I couldn't find that IP")
            return

        response.pop("readme", None)
        response.pop("status_code", None)

        embed = util.generate_embed_from_kwargs(
            title=f"IP info for {ip_address}", all_inline=True, **response
        )

        embed.set_thumbnail(url=self.IP_ICON_URL)
        embed.color = discord.Color.dark_green()

        await util.send_with_mention(ctx, embed=embed)
