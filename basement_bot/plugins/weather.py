import munch
from cogs import HttpPlugin
from discord import Embed
from discord.ext import commands
from utils.helpers import *


def setup(bot):
    bot.add_cog(Weather(bot))


class Weather(HttpPlugin):

    PLUGIN_NAME = __name__

    async def preconfig(self):
        if self.config.units == "imperial":
            self.temp_unit = "F"
        elif self.config.units == "metric":
            self.temp_unit = "C"
        else:
            self.temp_unit = "K"

    def get_url(self, args):
        searches = ",".join(map(str, args))
        url = "http://api.openweathermap.org/data/2.5/weather"
        return (
            f"{url}?q={searches}&units={self.config.units}&appid={self.config.dev_key}"
        )

    @commands.command(
        name="we",
        brief="Gives the weather",
        description="Returns the weather for a given area",
        usage="[city/town] [state-code] [country-code]",
    )
    async def we(self, ctx, *args):
        if not args:
            await priv_response(ctx, "I can't search for nothing!")
            return
        if len(args) > 3:
            args = args[:3]

        response = await self.http_call("get", self.get_url(args))
        if response.status_code == 404:
            await priv_response(ctx, "I could not find a location from your search!")
            return
        elif response.status_code != 200:
            await priv_response(
                ctx,
                "I had some trouble looking up the weather for you... try again later!",
            )
            return

        embed = self.generate_embed(munch.munchify(response.json()))
        await tagged_response(ctx, embed=embed)

    def generate_embed(self, response):
        embed = Embed(title=f"Weather for {response.name} ({response.sys.country})")

        descriptions = ", ".join(weather.description for weather in response.weather)
        embed.add_field(name="Description", value=descriptions, inline=False)

        embed.add_field(
            name=f"Temp ({self.temp_unit})",
            value=f"{int(response.main.temp)} (feels like {int(response.main.feels_like)})",
            inline=False,
        )
        embed.add_field(
            name=f"Low ({self.temp_unit})", value=int(response.main.temp_min)
        )
        embed.add_field(
            name=f"High ({self.temp_unit})",
            value=int(response.main.temp_max),
        )
        embed.add_field(name="Humidity", value=f"{int(response.main.humidity)} %")

        return embed
