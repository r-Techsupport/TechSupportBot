"""
This is a file to test the extensions/correct.py file
This contains 9 tests
"""

import importlib
from unittest.mock import AsyncMock

import pytest
from base import auxiliary

from . import config_for_tests


class Test_PrepareMessage:
    """A set of tests to test the prepare_message function"""

    def test_prepare_message_success(self):
        """Test to ensure that replacement when the entire message needs to be replaced works"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_content = discord_env.correct.prepare_message(
            discord_env.message_person2_noprefix_1.content, "message", "bbbb"
        )

        # Step 3 - Assert that everything works
        assert new_content == "**bbbb**"

    def test_prepare_message_multi(self):
        """Test to ensure that replacement works if multiple parts need to be replaced"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_content = discord_env.correct.prepare_message(
            discord_env.message_person2_noprefix_1.content, "e", "bbbb"
        )

        # Step 3 - Assert that everything works
        assert new_content == "m**bbbb**ssag**bbbb**"

    def test_prepare_message_partial(self):
        """Test to ensure that replacement works if multiple
        parts of the message need to be replaced"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_content = discord_env.correct.prepare_message(
            discord_env.message_person2_noprefix_1.content, "mes", "bbbb"
        )

        # Step 3 - Assert that everything works
        assert new_content == "**bbbb**sage"

    def test_prepare_message_fail(self):
        """Test to ensure that replacement doesnt change anything if needed
        This should never happen, but test it here anyway"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_content = discord_env.correct.prepare_message(
            discord_env.message_person2_noprefix_1.content, "asdf", "bbbb"
        )

        # Step 3 - Assert that everything works
        assert new_content == "message"


class Test_HandleCorrect:
    """Tests to test the handle_correct function"""

    @pytest.mark.asyncio
    async def test_handle_calls_search_for_message(self):
        """This ensures that the search_channel_for_message function is called,
        with the correct args"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.context.message = discord_env.message_person2_noprefix_1
        discord_env.correct.prepare_message = AsyncMock()
        auxiliary.search_channel_for_message = AsyncMock()
        auxiliary.generate_basic_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await discord_env.correct.correct_command(discord_env.context, "a", "b")

        # Step 3 - Assert that everything works
        auxiliary.search_channel_for_message.assert_called_once_with(
            channel=discord_env.channel,
            prefix=config_for_tests.PREFIX,
            content_to_match="a",
            allow_bot=False,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_handle_calls_prepare_message(self):
        """This ensures that the prepare_message function is called, with the correct args"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.context.message = discord_env.message_person2_noprefix_1
        discord_env.correct.prepare_message = AsyncMock()
        auxiliary.search_channel_for_message = AsyncMock(
            return_value=discord_env.message_person2_noprefix_1
        )
        auxiliary.generate_basic_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await discord_env.correct.correct_command(discord_env.context, "a", "b")

        # Step 3 - Assert that everything works
        discord_env.correct.prepare_message.assert_called_once_with(
            discord_env.message_person2_noprefix_1.content, "a", "b"
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_handle_calls_generate_embed(self):
        """This ensures that the generate_basic_embed function is called, with the correct args"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.context.message = discord_env.message_person2_noprefix_1
        discord_env.correct.prepare_message = AsyncMock()
        auxiliary.search_channel_for_message = AsyncMock(
            return_value=discord_env.message_person2_noprefix_1
        )
        auxiliary.generate_basic_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await discord_env.correct.correct_command(discord_env.context, "a", "b")

        # Step 3 - Assert that everything works
        auxiliary.generate_basic_embed.assert_called_once()

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_handle_calls_send(self):
        """This ensures that the ctx.send function is called, with the correct args"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.context.message = discord_env.message_person2_noprefix_1
        discord_env.correct.prepare_message = AsyncMock()
        auxiliary.search_channel_for_message = AsyncMock(
            return_value=discord_env.message_person2_noprefix_1
        )
        auxiliary.generate_basic_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await discord_env.correct.correct_command(discord_env.context, "a", "b")

        # Step 3 - Assert that everything works
        discord_env.context.send.assert_called_once()

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_handle_no_message_found(self):
        """This test ensures that a deny embed is sent if no message could be found"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        auxiliary.search_channel_for_message = AsyncMock(return_value=None)
        auxiliary.send_deny_embed = AsyncMock()

        # Step 2 - Call the function
        await discord_env.correct.correct_command(discord_env.context, "a", "b")

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="I couldn't find any message to correct",
            channel=discord_env.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)
