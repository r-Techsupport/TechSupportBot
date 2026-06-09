"""Module for the weather extension for the discord bot."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self

import discord
import munch
from discord import app_commands

from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Weather plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """
    await bot.add_cog(Weather(bot=bot))


class Weather(cogs.BaseCog):
    """Class to set up the weather extension for the discord bot."""

    async def preconfig(self: Self) -> None:
        """Loads the wmo-map.json file as self.wmo_map"""
        wmo_file = "resources/wmo-map.json"
        with open(wmo_file, "r", encoding="utf-8") as file:
            self.wmo_map = munch.munchify(json.load(file))

    @app_commands.command(
        name="weather",
        description="Gets weather data for a specific location",
    )
    async def get_weather(
        self: Self, interaction: discord.Interaction, city: str, country: str = None
    ) -> None:
        """This command gets weather from open-meteo and displays it in a fancy embed

        Args:
            interaction (discord.Interaction): The interaction that called this command
            city (str): The city to get weather for
            country (str, optional): If desired, the country to search in.
                Defaults to all countries.
        """
        await interaction.response.defer()
        geo_api_url = "https://geocoding-api.open-meteo.com/v1/search?name={}&count=10"
        weather_api_url = (
            "https://api.open-meteo.com/v1/forecast?"
            "latitude={}&longitude={}&current={}&daily={}&timezone=auto"
        )

        current_params = [
            "temperature_2m",
            "relative_humidity_2m",
            "wind_speed_10m",
            "apparent_temperature",
            "weather_code",
            "wind_direction_10m",
            "is_day",
        ]
        daily_params = ["temperature_2m_max", "temperature_2m_min"]
        current_params_str = ",".join(current_params)
        daily_params_str = ",".join(daily_params)

        fill_str = f"{city}" + (f"&country={country}" if country else "")
        filled_geo_url = geo_api_url.format(fill_str)
        geo_response = await self.bot.http_functions.http_call("get", filled_geo_url)

        if not geo_response or not geo_response.get("results"):
            embed = auxiliary.prepare_deny_embed(
                f"I was not able to find any locations matching {city}, {country}"
            )
            await interaction.followup.send(embed=embed)
            return

        if country:
            valid_locations = [
                entry
                for entry in geo_response.results
                if entry.country.lower() == country.lower()
            ]
        else:
            valid_locations = geo_response.results

        if not valid_locations:
            embed = auxiliary.prepare_deny_embed(
                f"I was not able to filter any locations matching {city}, {country}"
            )
            await interaction.followup.send(embed=embed)
            return

        city_name = valid_locations[0].name
        city_country = valid_locations[0].country
        latitude = valid_locations[0].latitude
        longitude = valid_locations[0].longitude
        filled_weather_url = weather_api_url.format(
            latitude, longitude, current_params_str, daily_params_str
        )
        weather_response = await self.bot.http_functions.http_call(
            "get", filled_weather_url
        )

        embed = self.generate_embed(city_name, city_country, weather_response)

        if not embed:
            embed = auxiliary.prepare_deny_embed(
                f"I was not able to get any weather for {city_name}, {city_country}"
            )
            await interaction.followup.send(embed=embed)
            return

        await interaction.followup.send(embed=embed)

    def generate_embed(
        self: Self, city_name: str, country_name: str, weather_response: munch.Munch
    ) -> discord.Embed | None:
        """This generates an embed from passed weather and location data

        Args:
            city_name (str): The name of the city the weather is for
            country_name (str): The name of the country the weather is for
            weather_response (munch.Munch): The raw response from the open meteo API

        Returns:
            discord.Embed | None: The embed that contains the weather data
        """
        try:
            embed = discord.Embed(title=f"Weather for {city_name}, {country_name}")
            daytime = bool(weather_response.current.is_day)

            wmo_code = str(weather_response.current.weather_code)

            if wmo_code in self.wmo_map:
                description = (
                    self.wmo_map[wmo_code].day.description
                    if daytime
                    else self.wmo_map[wmo_code].night.description
                )
                image = (
                    self.wmo_map[wmo_code].day.image
                    if daytime
                    else self.wmo_map[wmo_code].night.image
                )
                embed.add_field(
                    name="Description",
                    value=description,
                )
                embed.set_thumbnail(url=image)
            else:
                embed.add_field(
                    name="Description",
                    value=f"Unknown WMO code {wmo_code}",
                )

            embed.color = discord.Color.blurple()

            embed.add_field(
                name="Current temperature",
                value=format_temperature(weather_response.current.temperature_2m),
            )

            embed.add_field(
                name="Feels like",
                value=format_temperature(weather_response.current.apparent_temperature),
            )

            embed.add_field(
                name="Low temperature",
                value=format_temperature(weather_response.daily.temperature_2m_min[0]),
            )

            embed.add_field(
                name="High temperature",
                value=format_temperature(weather_response.daily.temperature_2m_max[0]),
            )

            embed.add_field(
                name="Humidity",
                value=f"{weather_response.current.relative_humidity_2m}%",
            )

            wind_direction = format_wind_direction(
                weather_response.current.wind_direction_10m
            )
            embed.add_field(
                name="Wind",
                value=f"{format_speed(weather_response.current.wind_speed_10m)} {wind_direction}",
            )

        except AttributeError:
            embed = None

        return embed


def format_temperature(temp_c: int) -> str:
    """This formats a temp given in celsius with the format:
    X°C (Y°F)

    Args:
        temp_c (int): The temp in celsius to process

    Returns:
        str: The formatted temp string
    """
    return f"{temp_c:.1f}°C ({convert_c_to_f(temp_c):.1f}°F)"


def format_speed(speed_kmh: int) -> str:
    """This formats a speed given in kilometers per hour with the format:
    X km/h (Y mph)

    Args:
        speed_kmh (int): The speed in kilometers per hour to process

    Returns:
        str: The formatted speed string
    """
    return f"{speed_kmh:.1f} km/h ({speed_kmh * 0.621371:.1f} mph)"


def convert_c_to_f(temp_c: int) -> float:
    """This converts celsius to fahrenheit

    Args:
        temp_c (int): The temp in celsius to convert

    Returns:
        float: The temperature in fahrenheit
    """
    return (temp_c * 9 / 5) + 32


def format_wind_direction(direction: int) -> str:
    """Converts a wind direction in degrees to a cardinal direction.

    Args:
        direction (int): The wind direction in degrees

    Returns:
        str: The cardinal direction
    """
    directions = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]

    return directions[round(direction / 22.5) % 16]
