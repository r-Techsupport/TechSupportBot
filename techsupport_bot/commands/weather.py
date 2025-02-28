"""Module for the weather extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import munch
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Weather plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.open_weather:
            raise AttributeError("Weather was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("Weather was not loaded due to missing API key") from exc

    await bot.add_cog(Weather(bot=bot))


class Weather(cogs.BaseCog):
    """Class to set up the weather extension for the discord bot."""

    def get_url(self: Self, args: list[str]) -> str:
        """Generates the url to fill in API keys and data

        Args:
            args (list[str]): The list of arguments passed by the user

        Returns:
            str: The API url formatted and ready to be called
        """
        filtered_args = filter(bool, args)
        searches = ",".join(map(str, filtered_args))
        url = "http://api.openweathermap.org/data/2.5/weather"
        filled_url = (
            f"{url}?q={searches}&units=imperial&appid"
            f"={self.bot.file_config.api.api_keys.open_weather}"
        )
        return filled_url

    @auxiliary.with_typing
    @commands.command(
        name="we",
        aliases=["weather", "wea"],
        brief="Searches for the weather",
        description=(
            "Returns the weather for a given area (this API sucks; I'm sorry in"
            " advance)"
        ),
        usage="[city/town] [state-code] [country-code]",
    )
    async def weather(
        self: Self,
        ctx: commands.Context,
        city_name: str,
        state_code: str = None,
        country_code: str = None,
    ) -> None:
        """This is the main logic for the weather command. This prepares the API data
        and sends a message to discord

        Args:
            ctx (commands.Context): The context generated by running this command
            city_name (str): For the API, the name of the city to get weather for
            state_code (str, optional): For the API, if applicable, the state code to search for.
                Defaults to None.
            country_code (str, optional): For the API, if needed you can add a country code to
                search for. Defaults to None.
        """
        response = await self.bot.http_functions.http_call(
            "get", self.get_url([city_name, state_code, country_code])
        )

        embed = self.generate_embed(munch.munchify(response))
        if not embed:
            await auxiliary.send_deny_embed(
                message="I could not find the weather from your search",
                channel=ctx.channel,
            )
            return

        await ctx.send(embed=embed)

    def generate_embed(self: Self, response: munch.Munch) -> discord.Embed | None:
        """Creates an embed filled with weather data:
        Current Temp
        High temp
        Low temp
        Humidity
        Condition

        Args:
            response (munch.Munch): The response from the API containing the weather data

        Returns:
            discord.Embed | None: Either the formatted embed, or nothing if the API failed
        """
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
                value=(
                    f"{int(response.main.temp)} (feels like"
                    f" {int(response.main.feels_like)})"
                ),
                inline=False,
            )
            embed.add_field(name="Low (F)", value=int(response.main.temp_min))
            embed.add_field(
                name="High (F)",
                value=int(response.main.temp_max),
            )
            embed.add_field(name="Humidity", value=f"{int(response.main.humidity)} %")
            embed.set_thumbnail(
                url=(
                    "https://www.iconarchive.com/download/i76758"
                    "/pixelkit/flat-jewels/Weather.512.png"
                )
            )
            embed.color = discord.Color.blurple()
        except AttributeError:
            embed = None

        return embed
