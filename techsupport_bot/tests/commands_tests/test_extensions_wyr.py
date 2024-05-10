"""
This is a file to test the extensions/wyr.py file
This contains 7 tests
"""

from __future__ import annotations

import importlib
import random
from typing import Self
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import discord
import pytest
from commands import wyr
from core import auxiliary
from tests import config_for_tests, helpers


def setup_local_extension(bot: helpers.MockBot = None) -> wyr.WouldYouRather:
    """A simple function to setup an instance of the wyr extension

    Args:
        bot (helpers.MockBot, optional): A fake bot object. Should be used if using a
            fake_discord_env in the test. Defaults to None.

    Returns:
        wyr.WouldYouRather: The instance of the WouldYouRather class
    """
    with patch("asyncio.create_task", return_value=None):
        return wyr.WouldYouRather(bot)


class Test_Preconfig:
    """A test to test the preconfig function"""

    @pytest.mark.asyncio
    async def test_preconfig(self: Self) -> None:
        """A test to ensure that preconfig sets the last variable correctly"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()

        # Step 2 - Call the function
        await wyr_test.preconfig()

        # Step 3 - Assert that everything works
        assert wyr_test.last is None


class Test_WYR_Command:
    """A set of tests to test the wyr command function"""

    @pytest.mark.asyncio
    async def test_wyr_command_embed(self: Self) -> None:
        """A test to ensure that the embed is generated correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        wyr_test = setup_local_extension(discord_env.bot)
        wyr_test.get_question = MagicMock(return_value='"real" || "question"')
        auxiliary.generate_basic_embed = MagicMock(return_value="embed")
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await wyr_test.wyr_command(discord_env.context)

        # Step 3 - Assert that everything works
        auxiliary.generate_basic_embed.assert_called_once_with(
            title="Would you rather...",
            description="Real, or question?",
            color=discord.Color.blurple(),
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_wyr_command_send(self: Self) -> None:
        """A test to ensure that the send command is called with the generated embed"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        wyr_test = setup_local_extension(discord_env.bot)
        wyr_test.get_question = MagicMock(return_value="Real question")
        auxiliary.generate_basic_embed = MagicMock(return_value="embed")
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await wyr_test.wyr_command(discord_env.context)

        # Step 3 - Assert that everything works
        discord_env.context.send.assert_called_once_with(embed="embed")

        # Step 4 - Cleanup
        importlib.reload(auxiliary)


class Test_Get_Question:
    """A set of tests to test the get_question function

    Attrs:
        sample_resource (str): A set of same questions for doing unit tests
    """

    sample_resource = '"q1o1" || "q1o2"\n"q2o1" || "q2o2"'

    def test_any_question(self: Self) -> None:
        """Ensure that get_question gets any question"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()
        wyr_test.last = None

        # Step 2 - Call the function
        with patch("builtins.open", mock_open(read_data=self.sample_resource)):
            question = wyr_test.get_question()

        # Step 3 - Assert that everything works
        assert isinstance(question, str)
        assert question != ""

    def test_resource_read(self: Self) -> None:
        """A test to ensure that the resource file is parsed correctly"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()
        wyr_test.last = None

        # Step 2 - Call the function
        with patch("builtins.open", mock_open(read_data=self.sample_resource)):
            question = wyr_test.get_question()

        # Step 3 - Assert that everything works
        assert question in ['"q1o1" || "q1o2"', '"q2o1" || "q2o2"']

        # Step 4 - Cleanup
        importlib.reload(random)

    def test_non_repeat_question(self: Self) -> None:
        """A test to ensure that a random question can never occur twice"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()
        wyr_test.last = '"q1o1" || "q1o2"'

        # Step 2 - Call the function
        with patch("builtins.open", mock_open(read_data=self.sample_resource)):
            question = wyr_test.get_question()

        # Step 3 - Assert that everything works
        assert question == '"q2o1" || "q2o2"'

        # Step 4 - Cleanup
        importlib.reload(random)

    def test_last_set(self: Self) -> None:
        """Ensure that the last variable is properly set"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()
        wyr_test.last = None

        # Step 2 - Call the function
        with patch("builtins.open", mock_open(read_data=self.sample_resource)):
            question = wyr_test.get_question()

        # Step 3 - Assert that everything works
        assert wyr_test.last is question

    def test_create_question_string(self: Self) -> None:
        """Ensure that the string is properly turned into
        a question"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()

        # Step 2 - Call the function
        resource_string = wyr_test.create_question_string('"q1o1" || "q1o2"')

        # Step 3 - Assert that everything works
        assert resource_string == "Q1o1, or q1o2?"
