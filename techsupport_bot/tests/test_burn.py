from functools import wraps
from unittest.mock import AsyncMock

import discord
import mock
import pytest
from discord.ext import commands
from extensions import Burn
from mock import patch


class MockMember:
    def __init__(self, id=None):
        self.id = id


class MockContext:
    def __init__(self, channel=None):
        self.channel = channel


class MockChannel:
    def __init__(self, history=None):
        self.message_history = history

    async def history(self, limit):
        for message in self.message_history:
            yield message


class MockMessage:
    def __init__(self, content=None, author=None):
        self.content = content
        self.author = author


@mock.patch("asyncio.create_task", return_value=None)
def test_generate_burn_embed(async_patch):
    burn = Burn("1")
    burn.PHRASES = ["Test Phrase"]
    embed = burn.generate_burn_embed()
    assert embed.color == discord.Color.red()
    assert embed.title == "Burn Alert!"
    assert embed.description == "🔥🔥🔥 Test Phrase 🔥🔥🔥"


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message(async_patch):
    burn = Burn("1")
    # Setup discord env
    member_to_burn = MockMember()
    message_to_burn = MockMessage(content="words", author=member_to_burn)
    message_history = [message_to_burn]
    channel = MockChannel(history=message_history)
    context = MockContext(channel=channel)

    returned_message = await burn.get_message(context, ".", member_to_burn)
    assert returned_message == message_to_burn


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message_late_in_list(async_patch):
    burn = Burn("1")
    # Setup discord env
    member_to_burn = MockMember()
    random_member = MockMember()
    random_message = MockMessage(content="by someone else", author=random_member)
    message_to_burn = MockMessage(content="Burned", author=member_to_burn)
    message_history = [
        random_message,
        random_message,
        random_message,
        random_message,
        message_to_burn,
    ]
    channel = MockChannel(history=message_history)
    context = MockContext(channel=channel)
    returned_message = await burn.get_message(context, ".", member_to_burn)
    assert returned_message == message_to_burn


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message_only_prefix(async_patch):
    burn = Burn("1")
    # Setup discord env
    member_to_burn = MockMember()
    message_to_burn = MockMessage(content=".words", author=member_to_burn)
    message_history = [message_to_burn]
    channel = MockChannel(history=message_history)
    context = MockContext(channel=channel)

    returned_message = await burn.get_message(context, ".", member_to_burn)
    assert returned_message == None


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_get_message_no_burn_messages(async_patch):
    burn = Burn("1")
    # Setup discord env
    member_to_burn = MockMember()
    random_member = MockMember()
    random_message = MockMessage(content="by someone else", author=random_member)
    message_history = [
        random_message,
        random_message,
        random_message,
        random_message,
        random_message,
        random_message,
        random_message,
        random_message,
    ]
    channel = MockChannel(history=message_history)
    context = MockContext(channel=channel)

    returned_message = await burn.get_message(context, ".", member_to_burn)
    assert returned_message == None


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_handle_burn(async_patch):
    burn = Burn("1")
    # Setup discord env
    member_to_burn = MockMember()
    message_to_burn = MockMessage(content="words", author=member_to_burn)
    message_history = [message_to_burn]
    channel = MockChannel(history=message_history)
    context = MockContext(channel=channel)
    message_to_burn.add_reaction = AsyncMock()
    context.send = AsyncMock()

    await burn.handle_burn(context, member_to_burn, message_to_burn)
    expected_calls = [
        mock.call("🔥"),
        mock.call("🚒"),
        mock.call("👨‍🚒"),
    ]
    message_to_burn.add_reaction.assert_has_calls(expected_calls, any_order=True)
    context.send.assert_called_once()


@pytest.mark.asyncio
@mock.patch("asyncio.create_task", return_value=None)
async def test_handle_burn_no_message(async_patch):
    burn = Burn("1")
    # Setup discord env
    context = MockContext()
    context.send_deny_embed = AsyncMock()

    await burn.handle_burn(context, None, None)

    context.send_deny_embed.assert_called_once()
