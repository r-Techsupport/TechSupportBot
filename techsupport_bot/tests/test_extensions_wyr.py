"""
This is a file to test the extensions/wyr.py file
This contains 7 tests
"""
import importlib
import random
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from base import auxiliary
from extensions import wyr

from . import config_for_tests


def setup_local_extension(bot=None):
    """A simple function to setup an instance of the wyr extension

    Args:
        bot (MockBot, optional): A fake bot object. Should be used if using a
        fake_discord_env in the test. Defaults to None.

    Returns:
        WouldYouRather: The instance of the WouldYouRather class
    """
    with patch("asyncio.create_task", return_value=None):
        return wyr.WouldYouRather(bot)


class Test_Question_Class:
    """A single test to test the Question class"""

    def test_str_question(self):
        """A test to ensure that the __str__ function is working"""
        # Step 1 - Setup env
        question = wyr.Question("Left", "Right")

        # Step 2 - Call the function
        text_question = str(question)

        # Step 3 - Assert that everything works
        assert text_question == "Left, or Right?"


class Test_Preconfig:
    """A test to test the preconfig function"""

    @pytest.mark.asyncio
    async def test_preconfig(self):
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
    async def test_wyr_command_embed(self):
        """A test to ensure that the embed is generated correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        wyr_test = setup_local_extension(discord_env.bot)
        wyr_test.get_question = MagicMock(return_value="Real question")
        auxiliary.generate_basic_embed = MagicMock(return_value="embed")
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await wyr_test.wyr_command(discord_env.context)

        # Step 3 - Assert that everything works
        auxiliary.generate_basic_embed.assert_called_once_with(
            title="Would you rather...",
            description="Real question",
            color=discord.Color.blurple(),
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_wyr_command_send(self):
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
    """A set of tests to test the get_question function"""

    def test_any_question(self):
        """Ensure that get_question gets any question"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()
        wyr_test.last = None

        # Step 2 - Call the function
        question = wyr_test.get_question()

        # Step 3 - Assert that everything works
        assert isinstance(question, wyr.Question)

    def test_non_repeat_question(self):
        """A test to ensure that a random question can never occur twice"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()
        wyr_test.QUESTIONS = [
            wyr.Question("left 1", "right 1"),
            wyr.Question("left 2", "right 2"),
        ]
        wyr_test.last = wyr_test.QUESTIONS[0]
        random.randint = MagicMock(return_value=0)

        # Step 2 - Call the function
        question = wyr_test.get_question()

        # Step 3 - Assert that everything works
        assert question is wyr_test.QUESTIONS[1]

        # Step 4 - Cleanup
        importlib.reload(random)

    def test_last_set(self):
        """Ensure that the last variable is properly set"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()
        wyr_test.last = None

        # Step 2 - Call the function
        question = wyr_test.get_question()

        # Step 3 - Assert that everything works
        assert wyr_test.last is question

    def test_wrap_around(self):
        """Ensure that get_question wraps around if needed"""
        # Step 1 - Setup env
        wyr_test = setup_local_extension()
        wyr_test.last = wyr_test.QUESTIONS[len(wyr_test.QUESTIONS) - 1]
        random.randint = MagicMock(return_value=len(wyr_test.QUESTIONS) - 1)

        # Step 2 - Call the function
        question = wyr_test.get_question()

        # Step 3 - Assert that everything works
        assert question is wyr_test.QUESTIONS[0]

        # Step 4 - Cleanup
        importlib.reload(random)
