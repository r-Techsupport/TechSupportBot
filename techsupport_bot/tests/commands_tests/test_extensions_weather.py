"""
This is a file to test the extensions/weather.py file
This contains tests for helper functions in weather.py
"""

from __future__ import annotations

from typing import Self

import munch
from commands import weather


class Test_BuildWeatherQuery:
    """Tests for build_weather_query"""

    def test_city_only(self: Self) -> None:
        """Ensures city-only query formatting works"""
        # Step 1 - Call the function
        query = weather.build_weather_query("Austin")

        # Step 2 - Assert that everything works
        assert query == "Austin"

    def test_three_parts(self: Self) -> None:
        """Ensures city/state/country formatting works"""
        # Step 1 - Call the function
        query = weather.build_weather_query("Austin", "TX", "US")

        # Step 2 - Assert that everything works
        assert query == "Austin,TX,US"

    def test_ignores_empty_parts(self: Self) -> None:
        """Ensures blank optional parts are removed from the query"""
        # Step 1 - Call the function
        query = weather.build_weather_query("Austin", "   ", None)

        # Step 2 - Assert that everything works
        assert query == "Austin"


class Test_BuildWeatherUrl:
    """Tests for build_weather_url"""

    def test_weather_url(self: Self) -> None:
        """Ensures API URL includes query, units, and key"""
        # Step 1 - Call the function
        url = weather.build_weather_url("Austin,TX,US", "ABC123")

        # Step 2 - Assert that everything works
        assert url == (
            "http://api.openweathermap.org/data/2.5/weather?"
            "q=Austin,TX,US&units=imperial&appid=ABC123"
        )


class Test_FahrenheitToCelsius:
    """Tests for fahrenheit_to_celsius"""

    def test_freezing_point(self: Self) -> None:
        """Ensures 32F converts to 0C"""
        # Step 1 - Call the function
        output = weather.fahrenheit_to_celsius(32)

        # Step 2 - Assert that everything works
        assert output == 0

    def test_boiling_point(self: Self) -> None:
        """Ensures 212F converts to 100C"""
        # Step 1 - Call the function
        output = weather.fahrenheit_to_celsius(212)

        # Step 2 - Assert that everything works
        assert output == 100


class Test_FormatDualTemperature:
    """Tests for format_dual_temperature"""

    def test_format_dual_temperature(self: Self) -> None:
        """Ensures dual-format temperature text renders correctly"""
        # Step 1 - Call the function
        output = weather.format_dual_temperature(68)

        # Step 2 - Assert that everything works
        assert output == "68°F (20°C)"


class Test_ExtractWeatherFields:
    """Tests for extract_weather_fields"""

    def test_valid_response(self: Self) -> None:
        """Ensures a valid response is converted to render-ready fields"""
        # Step 1 - Setup env
        response = munch.munchify(
            {
                "name": "Austin",
                "sys": {"country": "US"},
                "weather": [{"description": "clear sky"}, {"description": "dry"}],
                "main": {
                    "temp": 68,
                    "feels_like": 65,
                    "temp_min": 60,
                    "temp_max": 75,
                    "humidity": 45,
                },
            }
        )

        # Step 2 - Call the function
        fields = weather.extract_weather_fields(response)

        # Step 3 - Assert that everything works
        assert fields == {
            "title": "Weather for Austin (US)",
            "description": "clear sky, dry",
            "temp": "68°F (20°C) (feels like 65°F (18°C))",
            "low": "60°F (16°C)",
            "high": "75°F (24°C)",
            "humidity": "45 %",
        }

    def test_invalid_response(self: Self) -> None:
        """Ensures malformed responses return None"""
        # Step 1 - Setup env
        response = munch.munchify({"name": "Austin"})

        # Step 2 - Call the function
        fields = weather.extract_weather_fields(response)

        # Step 3 - Assert that everything works
        assert fields is None
