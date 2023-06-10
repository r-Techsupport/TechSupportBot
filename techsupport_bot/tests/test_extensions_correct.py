"""
This is a file to test the extensions/correct.py file
This contains 6 tests
"""

from unittest.mock import AsyncMock

import mock
import pytest
from base import auxiliary

from . import config_for_tests


class Test_PrepareMessage:
    """A set of tests to test the prepare_message function"""

    def test_prepare_message_success(self):
        """Test to ensure that replacement when the entire message needs to be replaced works"""
        with mock.patch("asyncio.create_task", return_value=None):
            discord_env = config_for_tests.FakeDiscordEnv()
            new_content = discord_env.correct.prepare_message(
                discord_env.message_person2_noprefix_1.content, "message", "bbbb"
            )
            assert new_content == "**bbbb**"

    def test_prepare_message_multi(self):
        """Test to ensure that replacement works if multiple parts need to be replaced"""
        with mock.patch("asyncio.create_task", return_value=None):
            discord_env = config_for_tests.FakeDiscordEnv()
            new_content = discord_env.correct.prepare_message(
                discord_env.message_person2_noprefix_1.content, "e", "bbbb"
            )
            assert new_content == "m**bbbb**ssag**bbbb**"

    def test_prepare_message_partial(self):
        """Test to ensure that replacement works if multiple
        parts of the message need to be replaced"""
        with mock.patch("asyncio.create_task", return_value=None):
            discord_env = config_for_tests.FakeDiscordEnv()
            new_content = discord_env.correct.prepare_message(
                discord_env.message_person2_noprefix_1.content, "mes", "bbbb"
            )
            assert new_content == "**bbbb**sage"

    def test_prepare_message_fail(self):
        """Test to ensure that replacement doesnt change anything if needed
        This should never happen, but test it here anyway"""
        with mock.patch("asyncio.create_task", return_value=None):
            discord_env = config_for_tests.FakeDiscordEnv()
            new_content = discord_env.correct.prepare_message(
                discord_env.message_person2_noprefix_1.content, "asdf", "bbbb"
            )
            assert new_content == "message"


class Test_HandleCorrect:
    """Tests to test the handle_correct function"""

    @pytest.mark.asyncio
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_handle_correct_positive(self, _):
        """This ensures that the correct functions are called during a successful correct command"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.context.message = discord_env.message_person2_noprefix_1
        discord_env.bot.get_prefix = AsyncMock(return_value=config_for_tests.PREFIX)
        discord_env.correct.find_message = AsyncMock()
        discord_env.correct.prepare_message = AsyncMock()
        auxiliary.search_channel_for_message = AsyncMock(
            return_value=discord_env.message_person2_noprefix_1
        )
        auxiliary.generate_basic_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        await discord_env.correct.correct_command(discord_env.context, "a", "b")

        auxiliary.search_channel_for_message.assert_called_once_with(
            channel=discord_env.channel,
            prefix=config_for_tests.PREFIX,
            content_to_match="a",
            allow_bot=False,
        )
        discord_env.correct.prepare_message.assert_called_once_with(
            discord_env.message_person2_noprefix_1.content, "a", "b"
        )
        auxiliary.generate_basic_embed.assert_called_once()
        discord_env.context.send.assert_called_once()

    @pytest.mark.asyncio
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_handle_correct_negative(self, _):
        """This test ensures that a deny embed is sent if no message could be found"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.bot.get_prefix = AsyncMock(return_value=config_for_tests.PREFIX)
        auxiliary.search_channel_for_message = AsyncMock(return_value=None)
        discord_env.context.send_deny_embed = AsyncMock()
        await discord_env.correct.correct_command(discord_env.context, "a", "b")

        auxiliary.search_channel_for_message.assert_called_once_with(
            channel=discord_env.channel,
            prefix=config_for_tests.PREFIX,
            content_to_match="a",
            allow_bot=False,
        )
        discord_env.context.send_deny_embed.assert_called_once_with(
            "I couldn't find any message to correct"
        )
