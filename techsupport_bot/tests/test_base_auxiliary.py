"""
This is a file to test the base/auxiliary.py file
This contains 15 tests
"""


from unittest.mock import AsyncMock, call

import discord
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
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person2_noprefix_1]

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel, content_to_match="message"
        )

        # Step 3 - Assert that everything works
        assert message == discord_env.message_person2_noprefix_1

    @pytest.mark.asyncio
    async def test_searching_only_member(self):
        """Test to ensure that member searching works"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person2_noprefix_1]

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel, member_to_match=discord_env.person2
        )

        # Step 3 - Assert that everything works
        assert message == discord_env.message_person2_noprefix_1

    @pytest.mark.asyncio
    async def test_searching_content_and_member(self):
        """Test to ensure that member and content searching works together"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person2_noprefix_1]

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel,
            member_to_match=discord_env.person2,
            content_to_match="message",
        )

        # Step 3 - Assert that everything works
        assert message == discord_env.message_person2_noprefix_1

    @pytest.mark.asyncio
    async def test_searching_ignore_prefix(self):
        """Test to ensure that a given prefix is ignored"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person1_prefix]

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel,
            prefix=config_for_tests.PREFIX,
            allow_bot=False,
        )

        # Step 3 - Assert that everything works
        assert message is None

    @pytest.mark.asyncio
    async def test_searching_keep_prefix(self):
        """Test to ensure that a given prefix is found"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person1_prefix]

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel, allow_bot=False
        )

        # Step 3 - Assert that everything works
        assert message == discord_env.message_person1_prefix

    @pytest.mark.asyncio
    async def test_searching_ignores_bot(self):
        """Test to ensure that bot messages are ignored"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person3_noprefix]

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel, allow_bot=False
        )

        # Step 3 - Assert that everything works
        assert message is None

    @pytest.mark.asyncio
    async def test_searching_finds_bot(self):
        """Test to ensure that bot messages are found"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = [discord_env.message_person3_noprefix]

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel, allow_bot=True
        )

        # Step 3 - Assert that everything works
        assert message == discord_env.message_person3_noprefix

    @pytest.mark.asyncio
    async def test_searching_member_multiple_messages(self):
        """Test to ensure that the most recent message is picked, if multiple match the critera"""
        # Step 1 - Setup env
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

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel, member_to_match=discord_env.person2
        )

        # Step 3 - Assert that everything works
        assert message == discord_env.message_person2_noprefix_2

    @pytest.mark.asyncio
    async def test_searching_by_member_not_first_message(self):
        """Test to ensure that the first message is not always picked"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        message_history = [
            discord_env.message_person1_noprefix_1,
            discord_env.message_person1_noprefix_1,
            discord_env.message_person1_noprefix_1,
            discord_env.message_person2_noprefix_2,
        ]
        discord_env.channel.message_history = message_history

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel, member_to_match=discord_env.person2
        )

        # Step 3 - Assert that everything works
        assert message == discord_env.message_person2_noprefix_2

    @pytest.mark.asyncio
    async def test_searching_by_nothing_returns_first_message(self):
        """Test to ensure that searching with no critera will always return the first message"""
        # Step 1 - Setup env
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

        # Step 2 - Call the function
        message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel
        )
        # Step 3 - Assert that everything works
        assert message == discord_env.message_person1_prefix

    @pytest.mark.asyncio
    @given(config_for_tests.rand_history())
    async def test_find_message_random_history(self, given_history):
        """Test to ensure that given a random history,
        the find message functions always works as expected"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.channel.message_history = given_history

        # Step 2 - Call the function
        found_message = await auxiliary.search_channel_for_message(
            channel=discord_env.channel,
            prefix=config_for_tests.PREFIX,
            content_to_match="a",
            allow_bot=False,
        )

        # Step 3 - Assert that everything works
        if found_message is not None:
            assert found_message.author.bot is False
            assert "a" in found_message.content
            assert not found_message.content.startswith(config_for_tests.PREFIX)


class Test_GenerateBasicEmbed:
    """Basic tests to test the generate_basic_embed function"""

    @given(text(), text())
    def test_generate_embed(self, title, description):
        """Property test to ensure that embeds are generated correctly"""
        # Step 2 - Call the function
        embed = auxiliary.generate_basic_embed(
            title=title, description=description, color=discord.Color.random()
        )

        # Step 3 - Assert that everything works
        assert embed.title == title
        assert embed.description == description
        assert isinstance(embed.color, discord.Color)

    def test_generate_embed_with_url(self):
        """Test to ensure that the URL property is added correctly"""
        # Step 2 - Call the function
        embed = auxiliary.generate_basic_embed(
            title="A",
            description="A",
            color=discord.Color.random(),
            url="https://a.com",
        )

        # Step 3 - Assert that everything works
        assert embed.thumbnail.url == "https://a.com"


class Test_AddReactions:
    """Basic tests to test add_list_of_reactions"""

    @pytest.mark.asyncio
    async def test_with_one_reaction(self):
        """Test add_list_of_reactions with just 1 emoji"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.message_person1_noprefix_1.add_reaction = AsyncMock()

        # Step 2 - Call the function
        await auxiliary.add_list_of_reactions(
            message=discord_env.message_person1_noprefix_1, reactions=["🔥"]
        )

        # Step 3 - Assert that everything works
        discord_env.message_person1_noprefix_1.add_reaction.assert_awaited_once_with(
            "🔥"
        )

    @pytest.mark.asyncio
    async def test_with_many_reaction(self):
        """Test add_list_of_reactions with just amny emoji"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.message_person1_noprefix_1.add_reaction = AsyncMock()

        # Step 2 - Call the function
        await auxiliary.add_list_of_reactions(
            message=discord_env.message_person1_noprefix_1,
            reactions=["🔥", "⬅️", "🗑️"],
        )

        # Step 3 - Assert that everything works
        expected_calls = [
            call("🔥"),
            call("⬅️"),
            call("🗑️"),
        ]
        discord_env.message_person1_noprefix_1.add_reaction.assert_has_calls(
            expected_calls, any_order=False
        )
