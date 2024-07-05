"""
This is a file to test the extensions/correct.py file
This contains 9 tests
"""

from __future__ import annotations

import importlib
from typing import Self
from unittest.mock import AsyncMock

import pytest
from core import auxiliary
from tests import config_for_tests
from commands import correct

class Test_PrepareMessage:
    """A set of tests to test the prepare_message function"""

    def test_prepare_message_success(self: Self) -> None:
        """Test to ensure that replacement when the entire message needs to be replaced works"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_content = correct.prepare_message(
            discord_env.message_person2_noprefix_1.content, "message", "bbbb"
        )

        # Step 3 - Assert that everything works
        assert new_content == "**bbbb**"

    def test_prepare_message_multi(self: Self) -> None:
        """Test to ensure that replacement works if multiple parts need to be replaced"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_content = correct.prepare_message(
            discord_env.message_person2_noprefix_1.content, "e", "bbbb"
        )

        # Step 3 - Assert that everything works
        assert new_content == "m**bbbb**ssag**bbbb**"

    def test_prepare_message_partial(self: Self) -> None:
        """Test to ensure that replacement works if multiple
        parts of the message need to be replaced"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_content = correct.prepare_message(
            discord_env.message_person2_noprefix_1.content, "mes", "bbbb"
        )

        # Step 3 - Assert that everything works
        assert new_content == "**bbbb**sage"

    def test_prepare_message_fail(self: Self) -> None:
        """Test to ensure that replacement doesnt change anything if needed
        This should never happen, but test it here anyway"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_content = correct.prepare_message(
            discord_env.message_person2_noprefix_1.content, "asdf", "bbbb"
        )

        # Step 3 - Assert that everything works
        assert new_content == "message"

