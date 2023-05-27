"""
This is a file to test the extensions/correct.py file
This contains 11 tests
"""

from unittest.mock import AsyncMock

import mock
import pytest
from base import auxiliary
from extensions import Corrector

from .helpers import MockBot, MockChannel, MockContext, MockMember, MockMessage

PREFIX = "."


class FakeDiscordEnv:
    """Class to setup the mock discord environment for the correct tests"""

    def __init__(self):
        self.bot = MockBot()
        self.person1 = MockMember(bot=False)
        self.person2 = MockMember(bot=False)
        self.person3 = MockMember(bot=True)
        self.message_prefix_person1 = MockMessage(
            content=f"{PREFIX}replace", author=self.person1
        )
        self.message_no_prefix_person2 = MockMessage(
            content="replace", author=self.person2
        )
        self.message_no_prefix_random_person1 = MockMessage(
            content="Random", author=self.person1
        )
        self.message_no_prefix_random_person2 = MockMessage(
            content="Random", author=self.person2
        )
        self.message_from_bot = MockMessage(content="replace", author=self.person3)
        self.channel = MockChannel()
        self.context = MockContext(channel=self.channel)
        self.correct = Corrector(self.bot)


def test_prepare_message_success():
    """Test to ensure that replacement when the entire message needs to be replaced works"""
    with mock.patch("asyncio.create_task", return_value=None):
        discord_env = FakeDiscordEnv()
        new_content = discord_env.correct.prepare_message(
            discord_env.message_no_prefix_person2.content, "replace", "bbbb"
        )
        assert new_content == "**bbbb**"


def test_prepare_message_multi():
    """Test to ensure that replacement works if multiple parts need to be replaced"""
    with mock.patch("asyncio.create_task", return_value=None):
        discord_env = FakeDiscordEnv()
        new_content = discord_env.correct.prepare_message(
            discord_env.message_no_prefix_person2.content, "e", "bbbb"
        )
        assert new_content == "r**bbbb**plac**bbbb**"


def test_prepare_message_partial():
    """Test to ensure that replacement works if multiple parts of the message need to be replaced"""
    with mock.patch("asyncio.create_task", return_value=None):
        discord_env = FakeDiscordEnv()
        new_content = discord_env.correct.prepare_message(
            discord_env.message_no_prefix_person2.content, "rep", "bbbb"
        )
        assert new_content == "**bbbb**lace"


def test_prepare_message_fail():
    """Test to ensure that replacement doesnt change anything if needed
    This should never happen, but test it here anyway"""
    with mock.patch("asyncio.create_task", return_value=None):
        discord_env = FakeDiscordEnv()
        new_content = discord_env.correct.prepare_message(
            discord_env.message_no_prefix_person2.content, "asdf", "bbbb"
        )
        assert new_content == "replace"


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_handle_correct_positive(_):
    """This ensures that the correct functions are called during a successful correct command"""
    discord_env = FakeDiscordEnv()
    discord_env.context.message = discord_env.message_no_prefix_person2
    discord_env.bot.get_prefix = AsyncMock(return_value=".")
    discord_env.correct.find_message = AsyncMock()
    discord_env.correct.prepare_message = AsyncMock()
    auxiliary.search_channel_for_message = AsyncMock(
        return_value=discord_env.message_no_prefix_person2
    )
    auxiliary.generate_basic_embed = AsyncMock()
    discord_env.context.send = AsyncMock()

    await discord_env.correct.handle_correct(discord_env.context, "a", "b")

    auxiliary.search_channel_for_message.assert_called_once_with(
        channel=discord_env.channel, prefix=".", content_to_match="a", allow_bot=False
    )
    discord_env.correct.prepare_message.assert_called_once_with(
        discord_env.message_no_prefix_person2.content, "a", "b"
    )
    auxiliary.generate_basic_embed.assert_called_once()
    discord_env.context.send.assert_called_once()


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_handle_correct_negative(_):
    """This test ensures that a deny embed is sent if no message could be found"""
    discord_env = FakeDiscordEnv()
    discord_env.bot.get_prefix = AsyncMock(return_value=".")
    auxiliary.search_channel_for_message = AsyncMock(return_value=None)
    discord_env.context.send_deny_embed = AsyncMock()
    await discord_env.correct.handle_correct(discord_env.context, "a", "b")

    auxiliary.search_channel_for_message.assert_called_once_with(
        channel=discord_env.channel, prefix=".", content_to_match="a", allow_bot=False
    )
    discord_env.context.send_deny_embed.assert_called_once_with(
        "I couldn't find any message to correct"
    )
