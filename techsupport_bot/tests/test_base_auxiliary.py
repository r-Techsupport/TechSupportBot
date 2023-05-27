"""
This is a file to test the base/auxiliary.py file
This contains 13 tests
"""
import random
from typing import Callable

import discord
import pytest
from base import auxiliary
from hypothesis import given
from hypothesis.strategies import composite, integers, text

from .helpers import MockChannel, MockContext, MockMember, MockMessage

PREFIX = "."


@composite
def rand_history(draw: Callable):
    """This is a custom strategy to generate a random message history"""
    hist_length = draw(integers(1, 30))
    final_history = []
    botPerson = MockMember(bot=True)
    nonBot = MockMember(bot=False)
    for _ in range(hist_length):
        temp_author = botPerson
        if bool(random.getrandbits(1)):
            temp_author = nonBot
        message = MockMessage(content=draw(text()), author=temp_author)
        final_history.append(message)
    return final_history


class FakeDiscordEnv:
    """Class to setup the mock discord environment for the correct tests"""

    def __init__(self):
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
        self.message_no_prefix_random_person2_message2 = MockMessage(
            content="Random 2", author=self.person2
        )
        self.message_from_bot = MockMessage(content="replace", author=self.person3)
        self.channel = MockChannel()
        self.context = MockContext(channel=self.channel)


@pytest.mark.asyncio
async def test_searching_only_content():
    """Test to ensure that content searching works"""
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_no_prefix_person2]
    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel, content_to_match="replace"
        )
        == discord_env.message_no_prefix_person2
    )


@pytest.mark.asyncio
async def test_searching_only_member():
    """Test to ensure that member searching works"""
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_no_prefix_person2]
    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel, member_to_match=discord_env.person2
        )
        == discord_env.message_no_prefix_person2
    )


@pytest.mark.asyncio
async def test_searching_content_and_member():
    """Test to ensure that member and content searching works together"""
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_no_prefix_person2]
    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel,
            member_to_match=discord_env.person2,
            content_to_match="replace",
        )
        == discord_env.message_no_prefix_person2
    )


@pytest.mark.asyncio
async def test_searching_ignore_prefix():
    """Test to ensure that a given prefix is ignored"""
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_prefix_person1]
    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel, prefix=PREFIX, allow_bot=False
        )
        == None
    )


@pytest.mark.asyncio
async def test_searching_keep_prefix():
    """Test to ensure that a given prefix is found"""
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_prefix_person1]
    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel, allow_bot=False
        )
        == discord_env.message_prefix_person1
    )


@pytest.mark.asyncio
async def test_searching_ignores_bot():
    """Test to ensure that bot messages are ignored"""
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_from_bot]
    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel, allow_bot=False
        )
        == None
    )


@pytest.mark.asyncio
async def test_searching_finds_bot():
    """Test to ensure that bot messages are found"""
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_from_bot]
    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel, allow_bot=True
        )
        == discord_env.message_from_bot
    )


@pytest.mark.asyncio
async def test_searching_member_multiple_messages():
    """Test to ensure that the most recent message is picked, if multiple match the critera"""
    discord_env = FakeDiscordEnv()

    message_history = [
        discord_env.message_no_prefix_random_person1,
        discord_env.message_no_prefix_random_person2,
        discord_env.message_no_prefix_random_person1,
        discord_env.message_no_prefix_random_person1,
        discord_env.message_no_prefix_random_person1,
        discord_env.message_no_prefix_random_person2_message2,
    ]
    discord_env.channel.message_history = message_history

    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel, member_to_match=discord_env.person2
        )
        == discord_env.message_no_prefix_random_person2
    )


@pytest.mark.asyncio
async def test_searching_by_member_not_first_message():
    """Test to ensure that the first message is not always picked"""
    discord_env = FakeDiscordEnv()

    message_history = [
        discord_env.message_no_prefix_random_person1,
        discord_env.message_no_prefix_random_person1,
        discord_env.message_no_prefix_random_person1,
        discord_env.message_no_prefix_random_person2,
    ]
    discord_env.channel.message_history = message_history

    assert (
        await auxiliary.search_channel_for_message(
            channel=discord_env.channel, member_to_match=discord_env.person2
        )
        == discord_env.message_no_prefix_random_person2
    )


@pytest.mark.asyncio
async def test_searching_by_nothing_returns_first_message():
    """Test to ensure that searching with no critera will always return the first message"""
    discord_env = FakeDiscordEnv()

    message_history = [
        discord_env.message_prefix_person1,
        discord_env.message_no_prefix_person2,
        discord_env.message_no_prefix_random_person1,
        discord_env.message_no_prefix_random_person2,
        discord_env.message_from_bot,
        discord_env.message_no_prefix_random_person2,
    ]
    discord_env.channel.message_history = message_history

    assert (
        await auxiliary.search_channel_for_message(channel=discord_env.channel)
        == discord_env.message_prefix_person1
    )


@pytest.mark.asyncio
@given(rand_history())
async def test_find_message_random_history(given_history):
    """Test to ensure that given a random history,
    the find message functions always works as expected"""
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = given_history
    found_message = await auxiliary.search_channel_for_message(
        channel=discord_env.channel,
        prefix=PREFIX,
        content_to_match="a",
        allow_bot=False,
    )
    if found_message is None:
        assert found_message is None
    else:
        assert found_message.author.bot == False
        assert "a" in found_message.content
        assert not found_message.content.startswith(PREFIX)


@given(text(), text())
def test_generate_embed(title, description):
    """Property test to ensure that embeds are generated correctly"""
    embed = auxiliary.generate_basic_embed(
        title=title, description=description, color=discord.Color.random()
    )
    assert embed.title == title
    assert embed.description in description
    assert isinstance(embed.color, discord.Color)


def test_generate_embed_with_url():
    """Test to ensure that the URL property is added correctly"""
    embed = auxiliary.generate_basic_embed(
        title="A", description="A", color=discord.Color.random(), url="https://a.com"
    )
    assert embed.thumbnail.url == "https://a.com"
