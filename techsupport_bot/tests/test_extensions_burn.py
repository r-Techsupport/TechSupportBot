"""
This is a file to test the extensions/burn.py file
This contains 3 tests
"""

from unittest.mock import AsyncMock

import mock
import pytest
from extensions import Burn

from .helpers import MockBot, MockChannel, MockContext, MockMember, MockMessage


class FakeDiscordEnv:
    """
    Class to setup the mock discord environment for the burn tests
    """

    def __init__(self):
        self.bot = MockBot()
        self.member_to_burn = MockMember(id=1)
        self.random_other_member = MockMember(id=2)
        self.message_to_burn = MockMessage(content="words", author=self.member_to_burn)
        self.message_to_burn_2 = MockMessage(
            content="words but more", author=self.member_to_burn
        )
        self.burn_message_with_prefix = MockMessage(
            content=".words", author=self.member_to_burn
        )
        self.random_message = MockMessage(
            content="words", author=self.random_other_member
        )
        self.channel = MockChannel()
        self.context = MockContext(channel=self.channel)
        self.burn = Burn(self.bot)


@mock.patch("asyncio.create_task", return_value=None)
def test_all_phrases_are_short(_):
    """
    This is a test to ensure that the generate burn embed function is working correctly
    This specifically looks at the description for every phrase in the PHRASES array
    This looks at the length of the description as well to ensure that the phrases aren't too long
    """
    discord_env = FakeDiscordEnv()

    test_phrases = discord_env.burn.PHRASES
    for phrase in test_phrases:
        assert len(f"🔥🔥🔥 {phrase} 🔥🔥🔥") <= 4096


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_handle_burn(_):
    """
    This is a test to ensure that handle_burn works correctly when a valid message can be found
    It checks to ensure that the reactions are added correctly,
        and that the send function was called
    """
    discord_env = FakeDiscordEnv()

    message_history = [discord_env.message_to_burn]
    discord_env.channel.message_history = message_history
    discord_env.message_to_burn.add_reaction = AsyncMock()
    discord_env.context.send = AsyncMock()

    await discord_env.burn.handle_burn(
        discord_env.context, discord_env.member_to_burn, discord_env.message_to_burn
    )
    expected_calls = [
        mock.call("🔥"),
        mock.call("🚒"),
        mock.call("👨‍🚒"),
    ]
    discord_env.message_to_burn.add_reaction.assert_has_calls(
        expected_calls, any_order=True
    )
    discord_env.context.send.assert_called_once()


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_handle_burn_no_message(_):
    """
    This is a test to ensure that the send_deny_embed function is called if no message can be found
    """
    discord_env = FakeDiscordEnv()

    discord_env.context.send_deny_embed = AsyncMock()

    await discord_env.burn.handle_burn(discord_env.context, None, None)
    discord_env.context.send_deny_embed.assert_called_once_with(
        "I could not a find a message to reply to"
    )
