"""
This is a file to test the extensions/echo.py file
This contains 5 tests
"""

from __future__ import annotations

from typing import Self

import munch
from commands import echo


class Test_NormalizeEchoMessage:
    """A set of tests for normalize_echo_message"""

    def test_keeps_regular_content(self: Self) -> None:
        """A test to ensure content without extra spaces is preserved"""
        # Step 1 - Call the function
        result = echo.normalize_echo_message("hello world")

        # Step 2 - Assert that everything works
        assert result == "hello world"

    def test_trims_outer_whitespace(self: Self) -> None:
        """A test to ensure leading and trailing whitespace are removed"""
        # Step 1 - Call the function
        result = echo.normalize_echo_message("   hello world   ")

        # Step 2 - Assert that everything works
        assert result == "hello world"

    def test_returns_no_content_for_blank(self: Self) -> None:
        """A test to ensure blank content is normalized to fallback text"""
        # Step 1 - Call the function
        result = echo.normalize_echo_message("    ")

        # Step 2 - Assert that everything works
        assert result == "No content"


class Test_BuildEchoChannelLogPayload:
    """A set of tests for build_echo_channel_log_payload"""

    def test_disabled_logger_returns_none(self: Self) -> None:
        """A test to ensure no payload is built if logger is disabled"""
        # Step 1 - Setup env
        config = munch.munchify({"enabled_extensions": ["echo"]})

        # Step 2 - Call the function
        result = echo.build_echo_channel_log_payload(config, "hello world")

        # Step 3 - Assert that everything works
        assert result is None

    def test_enabled_logger_returns_payload(self: Self) -> None:
        """A test to ensure payload is built correctly when logger is enabled"""
        # Step 1 - Setup env
        config = munch.munchify({"enabled_extensions": ["logger", "echo"]})

        # Step 2 - Call the function
        result = echo.build_echo_channel_log_payload(config, "   hello world  ")

        # Step 3 - Assert that everything works
        assert result == {
            "content_override": "hello world",
            "special_flags": ["Echo command"],
        }
