from discord.ext import commands

from cogs import HttpPlugin
from utils.helpers import get_env_value, priv_response


def setup(bot):
    bot.add_cog(ISSLocator(bot))


class ISSLocator(HttpPlugin):

    ISS_URL = "http://api.open-notify.org/iss-now.json"
    GEO_URL = "https://geocode.xyz/{},{}?geoit=json"

    @commands.command(
        name="iss",
        brief="Finds the International Space Station",
        description=("Returns the location of the International Space Station (ISS)."),
        help="\nLimitations: Sometimes the API may be down.",
    )
    async def iss(self, ctx):
        # get ISS coordinates
        response = await self.http_call("get", self.ISS_URL)
        if not response:
            await priv_response(
                ctx, "I had trouble calling the ISS API. Maybe it's down?"
            )
            return
        coordinates = response.json().get("iss_position", {})
        longitude, latitude = coordinates.get("longitude"), coordinates.get("latitude")
        if not longitude or not latitude:
            await priv_response(
                ctx, "I couldn't find the ISS coordinates from the API response"
            )
            return

        # get location information from coordinates
        location = None
        response = await self.http_call("get", self.GEO_URL.format(latitude, longitude))
        if not response:
            await priv_response(
                ctx, "I had trouble calling the GEO API. Maybe it's down?"
            )
            return
        else:
            osmtags = response.json().get("osmtags", {})
            location = osmtags.get("name")

        if not location:
            location = "Unknown"
        await ctx.send(
            f"`{location} @ {latitude},{longitude}` https://spotthestation.nasa.gov/tracking_map.cfm"
        )
