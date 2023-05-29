"""
This is a file to test the extensions/burn.py file
This contains 3 tests
"""

from unittest.mock import AsyncMock

import mock
import pytest
from base import auxiliary

from . import config_for_tests


class Test_Phrases:
    """A simple set of tests to ensure the PHRASES variable won't cause any problems"""

    @mock.patch("asyncio.create_task", return_value=None)
    def test_all_phrases_are_short(self, _):
        """
        This is a test to ensure that the generate burn embed function is working correctly
        This specifically looks at the description for every phrase in the PHRASES array
        This looks at the length of the description as well to ensure that
            the phrases aren't too long
        """
        discord_env = config_for_tests.FakeDiscordEnv()

        test_phrases = discord_env.burn.PHRASES
        for phrase in test_phrases:
            assert len(f"🔥🔥🔥 {phrase} 🔥🔥🔥") <= 4096


class Test_HandleBurn:
    """A set of test cases testing the handle_burn function"""

    @pytest.mark.asyncio
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_handle_burn(self, _):
        """
        This is a test to ensure that handle_burn works correctly when a valid message can be found
        It checks to ensure that the reactions are added correctly,
            and that the send function was called
        """
        discord_env = config_for_tests.FakeDiscordEnv()

        message_history = [discord_env.message_person1_noprefix_1]
        discord_env.channel.message_history = message_history
        discord_env.context.send = AsyncMock()

        auxiliary.add_list_of_reactions = AsyncMock()

        await discord_env.burn.handle_burn(
            discord_env.context,
            discord_env.person1,
            discord_env.message_person1_noprefix_1,
        )

        auxiliary.add_list_of_reactions.assert_called_once_with(
            message=discord_env.message_person1_noprefix_1, reactions=["🔥", "🚒", "👨‍🚒"]
        )

        discord_env.context.send.assert_called_once()

    @pytest.mark.asyncio
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_handle_burn_no_message(self, _):
        """
        This is a test to ensure that the send_deny_embed
            function is called if no message can be found
        """
        discord_env = config_for_tests.FakeDiscordEnv()

        discord_env.context.send_deny_embed = AsyncMock()

        await discord_env.burn.handle_burn(discord_env.context, None, None)
        discord_env.context.send_deny_embed.assert_called_once_with(
            "I could not a find a message to reply to"
        )
