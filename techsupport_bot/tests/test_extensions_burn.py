"""
This is a file to test the extensions/burn.py file
This contains 6 tests
"""

import importlib
from unittest.mock import AsyncMock

import pytest
from base import auxiliary

from . import config_for_tests


class Test_Phrases:
    """A simple set of tests to ensure the PHRASES variable won't cause any problems"""

    def test_all_phrases_are_short(self):
        """
        This is a test to ensure that the generate burn embed function is working correctly
        This specifically looks at the description for every phrase in the PHRASES array
        This looks at the length of the description as well to ensure that
            the phrases aren't too long
        """
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        test_phrases = discord_env.burn.PHRASES

        # Step 3 - Assert that everything works
        for phrase in test_phrases:
            assert len(f"🔥🔥🔥 {phrase} 🔥🔥🔥") <= 4096


class Test_HandleBurn:
    """A set of test cases testing the handle_burn function"""

    @pytest.mark.asyncio
    async def test_handle_burn_calls_reactions(self):
        """
        This is a test to ensure that handle_burn works correctly when a valid message can be found
        It checks to ensure that the reactions are added correctly
        """
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        message_history = [discord_env.message_person1_noprefix_1]
        discord_env.channel.message_history = message_history
        discord_env.context.send = AsyncMock()
        auxiliary.add_list_of_reactions = AsyncMock()

        # Step 2 - Call the function
        await discord_env.burn.handle_burn(
            discord_env.context,
            discord_env.person1,
            discord_env.message_person1_noprefix_1,
        )

        # Step 3 - Assert that everything works
        auxiliary.add_list_of_reactions.assert_called_once_with(
            message=discord_env.message_person1_noprefix_1,
            reactions=["🔥", "🚒", "👨‍🚒"],
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_handle_burn_calls_send(self):
        """
        This is a test to ensure that handle_burn works correctly when a valid message can be found
        It checks to ensure that the reactions are added correctly
        """
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        message_history = [discord_env.message_person1_noprefix_1]
        discord_env.channel.message_history = message_history
        discord_env.context.send = AsyncMock()
        auxiliary.add_list_of_reactions = AsyncMock()

        # Step 2 - Call the function
        await discord_env.burn.handle_burn(
            discord_env.context,
            discord_env.person1,
            discord_env.message_person1_noprefix_1,
        )

        # Step 3 - Assert that everything works
        discord_env.context.send.assert_called_once()

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_handle_burn_no_message(self):
        """
        This is a test to ensure that the send_deny_embed
            function is called if no message can be found
        """
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        auxiliary.send_deny_embed = AsyncMock()

        # Step 2 - Call the function
        await discord_env.burn.handle_burn(discord_env.context, None, None)

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="I could not a find a message to reply to",
            channel=discord_env.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)


class Test_BurnCommand:
    """A set of test cases for testing the burn_command function"""

    @pytest.mark.asyncio
    async def test_calls_search_channel(self):
        """A simple test to ensure that burn_command calls search_channel_for_message
        with the correct args"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        auxiliary.search_channel_for_message = AsyncMock()
        discord_env.burn.handle_burn = AsyncMock()

        # Step 2 - Call the function
        await discord_env.burn.burn_command(discord_env.context, discord_env.person1)

        # Step 3 - Assert that everything works
        auxiliary.search_channel_for_message.assert_called_once_with(
            channel=discord_env.context.channel,
            prefix=config_for_tests.PREFIX,
            member_to_match=discord_env.person1,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_calls_handle_burn(self):
        """A simple test to ensure that burn_command calls handle_burn
        with the correct args"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        auxiliary.search_channel_for_message = AsyncMock(
            return_value=discord_env.message_person1_noprefix_1
        )
        discord_env.burn.handle_burn = AsyncMock()

        # Step 2 - Call the function
        await discord_env.burn.burn_command(discord_env.context, discord_env.person1)

        # Step 3 - Assert that everything works
        discord_env.burn.handle_burn.assert_called_once_with(
            discord_env.context,
            discord_env.person1,
            discord_env.message_person1_noprefix_1,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)
