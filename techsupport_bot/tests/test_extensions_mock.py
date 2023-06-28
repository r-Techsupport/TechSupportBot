"""
This is a file to test the extensions/mock.py file
This contains 8 tests
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from base import auxiliary
from extensions import mock
from hypothesis import given
from hypothesis.strategies import text

from . import config_for_tests


def setup_local_extension(bot=None):
    """A simple function to setup an instance of the mock extension

    Args:
        bot (MockBot, optional): A fake bot object. Should be used if using a
        fake_discord_env in the test. Defaults to None.

    Returns:
        Mocker: The instance of the Mocker class
    """
    with patch("asyncio.create_task", return_value=None):
        return mock.Mocker(bot)


class Test_MockCommand:
    """A set of tests to test mock_command"""

    @pytest.mark.asyncio
    async def test_no_message(self):
        """A test to ensure that when no message is found, deny_embed is called"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        mocker = setup_local_extension(discord_env.bot)
        mocker.get_user_to_mock = MagicMock(return_value="username")
        mocker.generate_mock_message = AsyncMock(return_value=None)
        auxiliary.send_deny_embed = AsyncMock()

        # Step 2 - Call the function
        await mocker.mock_command(
            ctx=discord_env.context, input_user=discord_env.person2
        )

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="No message found for user username",
            channel=discord_env.context.channel,
        )

    @pytest.mark.asyncio
    async def test_send_call(self):
        """A test to ensure that ctx.send is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        mocker = setup_local_extension(discord_env.bot)
        mocker.get_user_to_mock = MagicMock()
        mocker.generate_mock_message = AsyncMock(return_value="message")
        auxiliary.send_deny_embed = AsyncMock()
        auxiliary.generate_basic_embed = MagicMock(return_value="embed")
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await mocker.mock_command(
            ctx=discord_env.context, input_user=discord_env.person2
        )

        # Step 3 - Assert that everything works
        discord_env.context.send.assert_called_once_with(embed="embed")


class Test_GenerateMockMessage:
    """A set of tests to test generate_mock_message"""

    @pytest.mark.asyncio
    async def test_no_message_found(self):
        """A test to ensure that when no message is found, None is returned"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        mocker = setup_local_extension(discord_env.bot)
        auxiliary.search_channel_for_message = AsyncMock(return_value=None)

        # Step 2 - Call the function
        result = await mocker.generate_mock_message(
            channel=discord_env.channel,
            user=discord_env.person2,
            prefix=config_for_tests.PREFIX,
        )

        # Step 3 - Assert that everything works
        assert result is None

    @pytest.mark.asyncio
    async def test_message_found(self):
        """A test to ensure that when a message is found, prepare_mock_message is called"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        mocker = setup_local_extension(discord_env.bot)
        mocker.prepare_mock_message = MagicMock()
        auxiliary.search_channel_for_message = AsyncMock(
            return_value=discord_env.message_person1_noprefix_1
        )

        # Step 2 - Call the function
        await mocker.generate_mock_message(
            channel=discord_env.channel,
            user=discord_env.person2,
            prefix=config_for_tests.PREFIX,
        )

        # Step 3 - Assert that everything works
        mocker.prepare_mock_message.assert_called_once_with(
            discord_env.message_person1_noprefix_1.clean_content
        )


class Test_GetUser:
    """A set of tests to test get_user_to_mock"""

    def test_with_bot(self):
        """A test to ensure that when a bot is mocked, the calling user is mocked instead"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        mocker = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = mocker.get_user_to_mock(
            ctx=discord_env.context, input_user=discord_env.person3_bot
        )

        # Step 3 - Assert that everything works
        assert result == discord_env.person1

    def test_without_bot(self):
        """A test to ensure that when not a bot is mocked, the same user is returned"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        mocker = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = mocker.get_user_to_mock(
            ctx=discord_env.context, input_user=discord_env.person1
        )

        # Step 3 - Assert that everything works
        assert result == discord_env.person1


class Test_PrepareMockMessage:
    """A set of tests to test prepare_mock_message"""

    def test_with_set_string(self):
        """A test to ensure that upper/lower works"""
        # Step 1 - Setup env
        mocker = setup_local_extension()

        # Step 2 - Call the function
        result = mocker.prepare_mock_message(message="abcd")

        # Step 3 - Assert that everything works
        assert result == "AbCd"

    @given(text())
    def test_with_random_string(self, input_message):
        """A property test to ensure that mocked message isn't getting smaller"""
        # Step 1 - Setup env
        mocker = setup_local_extension()

        # Step 2 - Call the function
        result = mocker.prepare_mock_message(message=input_message)

        # Step 3 - Assert that everything works
        assert len(result) >= len(input_message)
