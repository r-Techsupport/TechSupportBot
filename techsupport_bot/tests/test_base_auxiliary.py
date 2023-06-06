"""
This is a file to test the base/auxiliary.py file
This contains 15 tests
"""


from unittest.mock import AsyncMock

import discord
import mock
import pytest
from base import auxiliary
from hypothesis import given
from hypothesis.strategies import text

from . import config_for_tests


class Test_SearchForMessage:
    """A comprehensive set of tests to ensure that search_channel_for_message works"""

    @pytest.mark.asyncio
    async def test_searching_only_content(self):
        """Test to ensure that content searching works"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person2_noprefix_1]
        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel, content_to_match="message"
            )
            == discord_env.message_person2_noprefix_1
        )

    @pytest.mark.asyncio
    async def test_searching_only_member(self):
        """Test to ensure that member searching works"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person2_noprefix_1]
        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel, member_to_match=discord_env.person2
            )
            == discord_env.message_person2_noprefix_1
        )

    @pytest.mark.asyncio
    async def test_searching_content_and_member(self):
        """Test to ensure that member and content searching works together"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person2_noprefix_1]
        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel,
                member_to_match=discord_env.person2,
                content_to_match="message",
            )
            == discord_env.message_person2_noprefix_1
        )

    @pytest.mark.asyncio
    async def test_searching_ignore_prefix(self):
        """Test to ensure that a given prefix is ignored"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person1_prefix]
        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel,
                prefix=config_for_tests.PREFIX,
                allow_bot=False,
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_searching_keep_prefix(self):
        """Test to ensure that a given prefix is found"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person1_prefix]
        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel, allow_bot=False
            )
            == discord_env.message_person1_prefix
        )

    @pytest.mark.asyncio
    async def test_searching_ignores_bot(self):
        """Test to ensure that bot messages are ignored"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person3_noprefix]
        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel, allow_bot=False
            )
            is None
        )

    @pytest.mark.asyncio
    async def test_searching_finds_bot(self):
        """Test to ensure that bot messages are found"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person3_noprefix]
        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel, allow_bot=True
            )
            == discord_env.message_person3_noprefix
        )

    @pytest.mark.asyncio
    async def test_searching_member_multiple_messages(self):
        """Test to ensure that the most recent message is picked, if multiple match the critera"""
        discord_env = config_for_tests.FakeDiscordEnv()

        message_history = [
            discord_env.message_person1_noprefix_1,
            discord_env.message_person2_noprefix_2,
            discord_env.message_person1_noprefix_1,
            discord_env.message_person1_noprefix_1,
            discord_env.message_person1_noprefix_1,
            discord_env.message_person2_noprefix_3,
        ]
        discord_env.channel.message_history = message_history

        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel, member_to_match=discord_env.person2
            )
            == discord_env.message_person2_noprefix_2
        )

    @pytest.mark.asyncio
    async def test_searching_by_member_not_first_message(self):
        """Test to ensure that the first message is not always picked"""
        discord_env = config_for_tests.FakeDiscordEnv()

        message_history = [
            discord_env.message_person1_noprefix_1,
            discord_env.message_person1_noprefix_1,
            discord_env.message_person1_noprefix_1,
            discord_env.message_person2_noprefix_2,
        ]
        discord_env.channel.message_history = message_history

        assert (
            await auxiliary.search_channel_for_message(
                channel=discord_env.channel, member_to_match=discord_env.person2
            )
            == discord_env.message_person2_noprefix_2
        )

    @pytest.mark.asyncio
    async def test_searching_by_nothing_returns_first_message(self):
        """Test to ensure that searching with no critera will always return the first message"""
        discord_env = config_for_tests.FakeDiscordEnv()

        message_history = [
            discord_env.message_person1_prefix,
            discord_env.message_person2_noprefix_1,
            discord_env.message_person1_noprefix_1,
            discord_env.message_person2_noprefix_2,
            discord_env.message_person3_noprefix,
            discord_env.message_person2_noprefix_2,
        ]
        discord_env.channel.message_history = message_history

        assert (
            await auxiliary.search_channel_for_message(channel=discord_env.channel)
            == discord_env.message_person1_prefix
        )

    @pytest.mark.asyncio
    @given(config_for_tests.rand_history())
    async def test_find_message_random_history(self, given_history):
        """Test to ensure that given a random history,
        the find message functions always works as expected"""
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = given_history
        found_message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel,
            prefix=config_for_tests.PREFIX,
            content_to_match="a",
            allow_bot=False,
        )
        if found_message is None:
            assert found_message is None
        else:
            assert found_message.author.bot is False
            assert "a" in found_message.content
            assert not found_message.content.startswith(config_for_tests.PREFIX)


class Test_GenerateBasicEmbed:
    """Basic tests to test the generate_basic_embed function"""

    @given(text(), text())
    def test_generate_embed(self, title, description):
        """Property test to ensure that embeds are generated correctly"""
        embed = auxiliary.generate_basic_embed(
            title=title, description=description, color=discord.Color.random()
        )
        assert embed.title == title
        assert embed.description == description
        assert isinstance(embed.color, discord.Color)

    def test_generate_embed_with_url(self):
        """Test to ensure that the URL property is added correctly"""
        embed = auxiliary.generate_basic_embed(
            title="A",
            description="A",
            color=discord.Color.random(),
            url="https://a.com",
        )
        assert embed.thumbnail.url == "https://a.com"


class Test_AddReactions:
    """Basic tests to test add_list_of_reactions"""

    @pytest.mark.asyncio
    async def test_with_one_reaction(self):
        """Test add_list_of_reactions with just 1 emoji"""
        with mock.patch("asyncio.create_task", return_value=None):
            discord_env = config_for_tests.FakeDiscordEnv()
            discord_env.message_person1_noprefix_1.add_reaction = AsyncMock()
            await auxiliary.add_list_of_reactions(
                message=discord_env.message_person1_noprefix_1, reactions=["🔥"]
            )
            discord_env.message_person1_noprefix_1.add_reaction.assert_awaited_once_with(
                "🔥"
            )

    @pytest.mark.asyncio
    async def test_with_many_reaction(self):
        """Test add_list_of_reactions with just amny emoji"""
        with mock.patch("asyncio.create_task", return_value=None):
            discord_env = config_for_tests.FakeDiscordEnv()
            discord_env.message_person1_noprefix_1.add_reaction = AsyncMock()
            await auxiliary.add_list_of_reactions(
                message=discord_env.message_person1_noprefix_1,
                reactions=["🔥", "⬅️", "🗑️"],
            )
            expected_calls = [
                mock.call("🔥"),
                mock.call("⬅️"),
                mock.call("🗑️"),
            ]
        discord_env.message_person1_noprefix_1.add_reaction.assert_has_calls(
            expected_calls, any_order=False
        )
