"""Module for the weather extension for the discord bot."""
import base
import discord
import munch
import util
from discord.ext import commands


def setup(bot):
    """Adding the weather configuration to the config file."""
    bot.add_cog(Weather(bot=bot))


class Weather(base.BaseCog):
    """Class to set up the weather extension for the discord bot."""

    def get_url(self, args):
        """Method to get the API for the weather command."""
        filtered_args = filter(bool, args)
        searches = ",".join(map(str, filtered_args))
        url = "http://api.openweathermap.org/data/2.5/weather"
        return f"{url}?q={searches}&units=imperial&appid={self.bot.file_config.main.api_keys.open_weather}"

    @util.with_typing
    @commands.cooldown(3, 60, commands.BucketType.channel)
    @commands.command(
        name="we",
        aliases=["weather", "wea"],
        brief="Searches for the weather",
        description="Returns the weather for a given area (this API sucks; I'm sorry in advance)",
        usage="[city/town] [state-code] [country-code]",
    )
    async def weather(
        self, ctx, city_name: str, state_code: str = None, country_code: str = None
    ):
        """Method to define the weather for the command."""
        response = await self.bot.http_call(
            "get", self.get_url([city_name, state_code, country_code])
        )

        embed = self.generate_embed(munch.munchify(response))
        if not embed:
            await ctx.send_deny_embed("I could not find the weather from your search")
            return

        await ctx.send(embed=embed)

    def generate_embed(self, response):
        """Method to generate the embed for the weather command."""
        try:
            embed = discord.Embed(
                title=f"Weather for {response.name} ({response.sys.country})"
            )

            descriptions = ", ".join(
                weather.description for weather in response.weather
            )
            embed.add_field(name="Description", value=descriptions, inline=False)

            embed.add_field(
                name="Temp (F)",
                value=f"{int(response.main.temp)} (feels like {int(response.main.feels_like)})",
                inline=False,
            )
            embed.add_field(name="Low (F)", value=int(response.main.temp_min))
            embed.add_field(
                name="High (F)",
                value=int(response.main.temp_max),
            )
            embed.add_field(name="Humidity", value=f"{int(response.main.humidity)} %")
            embed.set_thumbnail(
                url="https://cdn.icon-icons.com/icons2/8/PNG/256/cloudyweather_cloud_inpart_day_wind_thunder_sunny_rain_darkness_nublad_1459.png"
            )
            embed.color = discord.Color.blurple()
        except AttributeError:
            embed = None

        return embed
