import random
from typing import Callable

import discord
import mock
import pytest
from extensions import Corrector
from hypothesis import given
from hypothesis.strategies import composite, integers, text

from .helpers import MockBot, MockChannel, MockContext, MockMember, MockMessage

PREFIX = "."


@composite
def rand_history(draw: Callable):
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


@given(text())
def test_generate_embed(content):
    with mock.patch("asyncio.create_task", return_value=None):
        discord_env = FakeDiscordEnv()
        embed = discord_env.correct.generate_embed(content)
        assert embed.title == "Correction!"
        assert embed.description == f"{content} :white_check_mark:"
        assert embed.color == discord.Color.green()


@pytest.mark.asyncio
async def test_find_message_success():
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_no_prefix_person2]
    assert (
        await discord_env.correct.find_message(discord_env.context, PREFIX, "replace")
        == discord_env.message_no_prefix_person2
    )


@pytest.mark.asyncio
async def test_find_message_only_prefix():
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_prefix_person1]
    assert (
        await discord_env.correct.find_message(discord_env.context, PREFIX, "replace")
        == None
    )


@pytest.mark.asyncio
async def test_find_message_only_bot():
    discord_env = FakeDiscordEnv()
    discord_env.channel.message_history = [discord_env.message_from_bot]
    assert (
        await discord_env.correct.find_message(discord_env.context, PREFIX, "replace")
        == None
    )


@pytest.mark.asyncio
@given(rand_history())
async def test_find_message_random_history(given_history):
    with mock.patch("asyncio.create_task", return_value=None):
        discord_env = FakeDiscordEnv()
        discord_env.channel.message_history = given_history
        found_message = await discord_env.correct.find_message(
            discord_env.context, PREFIX, "a"
        )
        if found_message is None:
            assert found_message is None
        else:
            assert found_message.author.bot == False
            assert "a" in found_message.content
            assert not found_message.content.startswith(PREFIX)
