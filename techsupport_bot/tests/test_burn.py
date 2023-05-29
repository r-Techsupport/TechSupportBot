"""
This is a file to test the extensions/burn.py file
This contains 11 unit tests
8 tests handle the expected postive outcome
3 tests handle negative outcomes/error handling
"""

from unittest.mock import AsyncMock

import discord
import mock
import pytest
from extensions import Burn, setup

from .helpers import MockBot, MockChannel, MockContext, MockMember, MockMessage


# pylint: disable=too-many-instance-attributes
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


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_setup(_):
    """
    This is a simple test to ensure that the setup function works correctly
    """
    discord_env = FakeDiscordEnv()

    discord_env.bot.add_cog = AsyncMock()

    await setup(discord_env.bot)
    discord_env.bot.add_cog.assert_called_once()


@mock.patch("asyncio.create_task", return_value=None)
def test_generate_burn_embed(_):
    """
    This is a test to ensure that the generate burn embed function is working correctly
    It looks to ensure that the color, title, and description are formatted correctly
    """
    discord_env = FakeDiscordEnv()

    discord_env.burn.PHRASES = ["Test Phrase"]

    embed = discord_env.burn.generate_burn_embed()
    assert embed.color == discord.Color.red()
    assert embed.title == "Burn Alert!"
    assert embed.description == "🔥🔥🔥 Test Phrase 🔥🔥🔥"


@mock.patch("asyncio.create_task", return_value=None)
def test_generate_burn_embed_all_phrases(_):
    """
    This is a test to ensure that the generate burn embed function is working correctly
    This specifically looks at the description for every phrase in the PHRASES array
    This looks at the length of the description as well to ensure that the phrases aren't too long
    """
    discord_env = FakeDiscordEnv()

    test_phrases = discord_env.burn.PHRASES
    for phrase in test_phrases:
        discord_env.burn.PHRASES = [phrase]
        embed = discord_env.burn.generate_burn_embed()
        assert embed.description == f"🔥🔥🔥 {phrase} 🔥🔥🔥"
        assert len(embed.description) <= 4096


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message(_):
    """
    This is a test to check if get_message works when a valid message is found in the history
    """
    discord_env = FakeDiscordEnv()

    message_history = [discord_env.message_to_burn]
    discord_env.channel.message_history = message_history

    returned_message = await discord_env.burn.get_message(
        discord_env.context, ".", discord_env.member_to_burn
    )
    assert returned_message == discord_env.message_to_burn


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message_multiple_messages(_):
    """
    This is a test to check if get_message works when a valid message is found in the history, if
        there is more than 1 message from the member to burn in the history
    """
    discord_env = FakeDiscordEnv()

    message_history = [
        discord_env.random_message,
        discord_env.message_to_burn,
        discord_env.random_message,
        discord_env.random_message,
        discord_env.random_message,
        discord_env.message_to_burn_2,
    ]
    discord_env.channel.message_history = message_history

    returned_message = await discord_env.burn.get_message(
        discord_env.context, ".", discord_env.member_to_burn
    )
    assert returned_message == discord_env.message_to_burn


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message_prefix_non_prefix(_):
    """
    This is a test to check if get_message works when a valid message is found in the history, if
        there is more than 1 message from the member to burn in the history,
        but only 1 without the prefix
    """
    discord_env = FakeDiscordEnv()

    message_history = [
        discord_env.random_message,
        discord_env.burn_message_with_prefix,
        discord_env.message_to_burn,
    ]
    discord_env.channel.message_history = message_history

    returned_message = await discord_env.burn.get_message(
        discord_env.context, ".", discord_env.member_to_burn
    )
    assert returned_message == discord_env.message_to_burn


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message_late_in_list(_):
    """
    This is a test to see if get_message works when a valid message
        is found in the history, but only after other messages are sent as well
    """
    discord_env = FakeDiscordEnv()

    message_history = [
        discord_env.random_message,
        discord_env.random_message,
        discord_env.random_message,
        discord_env.random_message,
        discord_env.message_to_burn,
    ]
    discord_env.channel.message_history = message_history

    returned_message = await discord_env.burn.get_message(
        discord_env.context, ".", discord_env.member_to_burn
    )
    assert returned_message == discord_env.message_to_burn


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message_only_prefix(_):
    """
    This is a test to see if get_message returns None when
        the only message from the burned member is a bot command
    """
    discord_env = FakeDiscordEnv()

    message_history = [discord_env.burn_message_with_prefix]
    discord_env.channel.message_history = message_history

    returned_message = await discord_env.burn.get_message(
        discord_env.context, ".", discord_env.member_to_burn
    )
    assert returned_message == None


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message_no_burn_messages(_):
    """
    This is a test to ensure that get_message returns None when
        no messages from the burned member are in the history
    """
    discord_env = FakeDiscordEnv()

    message_history = [discord_env.random_message] * 20
    discord_env.channel.message_history = message_history

    returned_message = await discord_env.burn.get_message(
        discord_env.context, ".", discord_env.member_to_burn
    )
    assert returned_message == None


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
