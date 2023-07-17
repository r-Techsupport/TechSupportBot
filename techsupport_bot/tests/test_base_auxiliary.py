"""
This is a file to test the base/auxiliary.py file
This contains 23 tests
"""


import importlib
from unittest.mock import AsyncMock, MagicMock, call

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


class Test_ConstructMention:
    """A set of test cases to test construct_mention_string"""

    def test_no_users(self):
        """Test that if no users are passed, the mention string is blank"""
        # Step 2 - Call the function
        output = auxiliary.construct_mention_string([None])

        # Step 3 - Assert that everything works
        assert output == None

    def test_one_user(self):
        """Test that if only 1 user is passed, the mention string contains the proper mention"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        output = auxiliary.construct_mention_string([discord_env.person1])

        # Step 3 - Assert that everything works
        assert output == discord_env.person1.mention

    def test_two_users(self):
        """Test that if 2 users are passed, the mention string contains both,
        and is seperated by a space"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        output = auxiliary.construct_mention_string(
            [discord_env.person1, discord_env.person2]
        )

        # Step 3 - Assert that everything works
        assert output == f"{discord_env.person1.mention} {discord_env.person2.mention}"

    def test_mulltiple_same_user(self):
        """Test that is mutliple of the same user is passed, the mention
        string only contains the mention once"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        output = auxiliary.construct_mention_string(
            [discord_env.person1, discord_env.person1]
        )

        # Step 3 - Assert that everything works
        assert output == discord_env.person1.mention


class Test_DenyEmbed:
    """Tests for prepare_deny_embed and send_deny_embed"""

    def test_prepare_deny(self):
        """Test that the deny embed is working correctly, and that the parameters are correct"""
        # Step 1 - Setup env
        auxiliary.generate_basic_embed = MagicMock()

        # Step 2 - Call the function
        auxiliary.prepare_deny_embed("Test")

        # Step 3 - Assert that everything works
        auxiliary.generate_basic_embed.assert_called_once_with(
            title="😕 👎",
            description="Test",
            color=discord.Color.red(),
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_send_deny(self):
        """Test that send deny embed sends the right content to the right place"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        auxiliary.prepare_deny_embed = MagicMock(return_value="test")
        auxiliary.construct_mention_string = MagicMock(return_value="")
        discord_env.channel.send = AsyncMock()

        # Step 2 - Call the function
        await auxiliary.send_deny_embed("Message", discord_env.channel)

        # Step 3 - Assert that everything works
        discord_env.channel.send.assert_awaited_once_with(content="", embed="test")

        # Step 4 - Cleanup
        importlib.reload(auxiliary)


class Test_ConfirmEmbed:
    """Tests for prepare_confirm_embed and send_confirm_embed"""

    def test_prepare_confirm(self):
        """Test that the confirm embed is working correctly, and that the parameters are correct"""
        # Step 1 - Setup env
        auxiliary.generate_basic_embed = MagicMock()

        # Step 2 - Call the function
        auxiliary.prepare_confirm_embed("Test")

        # Step 3 - Assert that everything works
        auxiliary.generate_basic_embed.assert_called_once_with(
            title="😄 👍",
            description="Test",
            color=discord.Color.green(),
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_send_confirm(self):
        """Test that send confirm embed sends the right content to the right place"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        auxiliary.prepare_confirm_embed = MagicMock(return_value="test")
        auxiliary.construct_mention_string = MagicMock(return_value="")
        discord_env.channel.send = AsyncMock()

        # Step 2 - Call the function
        await auxiliary.send_confirm_embed("Message", discord_env.channel)

        # Step 3 - Assert that everything works
        discord_env.channel.send.assert_awaited_once_with(content="", embed="test")

        # Step 4 - Cleanup
        importlib.reload(auxiliary)
