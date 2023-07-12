"""
This is a file to test the extensions/emoji.py file
This contains 14 tests
"""


import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from base import auxiliary

from . import config_for_tests


class Test_EmojiFromChar:
    """A class to test the emoji_from_char method"""

    def test_lowercase_letter(self):
        """A test to ensure that a lowercase letter returns correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        char = discord_env.emoji.emoji_from_char("a")

        # Step 3 - Assert that everything works
        assert char == "🇦"

    def test_uppercase_letter(self):
        """A test to ensure that a uppsercase letter returns correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        char = discord_env.emoji.emoji_from_char("A")

        # Step 3 - Assert that everything works
        assert char == "🇦"

    def test_number(self):
        """A test to ensure that a number returns correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        char = discord_env.emoji.emoji_from_char("1")

        # Step 3 - Assert that everything works
        assert char == "1️⃣"

    def test_question_mark(self):
        """A test to ensure that a uppsercase letter returns correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        char = discord_env.emoji.emoji_from_char("?")

        # Step 3 - Assert that everything works
        assert char == "❓"

    def test_invalid(self):
        """A test to ensure that a uppsercase letter returns correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        char = discord_env.emoji.emoji_from_char("]")

        # Step 3 - Assert that everything works
        assert char is None


class Test_CheckIfAllUnique:
    """A class to test the check_if_all_unique method"""

    def test_unique(self):
        """Test to ensure that a unique string is detected"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        response = discord_env.emoji.check_if_all_unique("abcde")

        # Step 3 - Assert that everything works
        assert response

    def test_non_unique(self):
        """Test to ensure that a non-unique string is detected"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        response = discord_env.emoji.check_if_all_unique("abcade")

        # Step 3 - Assert that everything works
        assert not response


class Test_GenerateEmojiString:
    """A class to test the generate_emoji_string method"""

    def test_only_emoji(self):
        """Test to ensure that only_emoji works when true"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        response = discord_env.emoji.generate_emoji_string("abcd!@#$1234", True)

        # Step 3 - Assert that everything works
        assert len(response) == 9
        assert response == ["🇦", "🇧", "🇨", "🇩", "❗", "1️⃣", "2️⃣", "3️⃣", "4️⃣"]

    def test_non_emoji(self):
        """Test to ensure that only_emoji works when false"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        response = discord_env.emoji.generate_emoji_string("abcd!@#$1234", False)

        # Step 3 - Assert that everything works
        assert len(response) == 12
        assert response == [
            "🇦",
            "🇧",
            "🇨",
            "🇩",
            "❗",
            "@",
            "#",
            "$",
            "1️⃣",
            "2️⃣",
            "3️⃣",
            "4️⃣",
        ]


class Test_EmojiCommands:
    """A class to test the emoji_commands method"""

    @pytest.mark.asyncio
    async def test_empty_string(self):
        """Test to ensure that an error is thrown on a empty response"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.emoji.generate_emoji_string = MagicMock(return_value=[])
        auxiliary.send_deny_embed = AsyncMock()

        # Step 2 - Call the function
        await discord_env.emoji.emoji_commands(discord_env.context, "abcde", False)

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="I can't get any emoji letters from your message!",
            channel=discord_env.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_find_no_message(self):
        """Test to ensure that if no message could be found, an error will occur"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.emoji.generate_emoji_string = MagicMock(return_value=["1"])
        auxiliary.search_channel_for_message = AsyncMock(return_value=None)
        auxiliary.send_deny_embed = AsyncMock()

        # Step 2 - Call the function
        await discord_env.emoji.emoji_commands(
            discord_env.context, "abcde", False, "Fake discord user"
        )

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="No valid messages found to react to!", channel=discord_env.channel
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_unique_error(self):
        """Test to ensure that if the string is not unique, an error will occur"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.emoji.generate_emoji_string = MagicMock(return_value=["1"])
        discord_env.emoji.check_if_all_unique = MagicMock(return_value=False)
        auxiliary.send_deny_embed = AsyncMock()

        # Step 2 - Call the function
        await discord_env.emoji.emoji_commands(discord_env.context, "abcde", True)

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="Invalid message! Make sure there are no repeat characters!",
            channel=discord_env.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_confirm_with_proper_call(self):
        """Test that send_confirm_embed is being called with the proper string"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.emoji.generate_emoji_string = MagicMock(return_value=["1", "2"])
        auxiliary.send_confirm_embed = AsyncMock()

        # Step 2 - Call the function
        await discord_env.emoji.emoji_commands(discord_env.context, "abcde", False)

        # Step 3 - Assert that everything works
        auxiliary.send_confirm_embed.assert_called_once_with(
            message="1 2", channel=discord_env.channel
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_proper_reactions(self):
        """Test that send_confirm_embed is being called with the proper string"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        discord_env.emoji.generate_emoji_string = MagicMock(return_value=["1", "2"])
        auxiliary.search_channel_for_message = AsyncMock(
            return_value=discord_env.message_person1_noprefix_1
        )
        auxiliary.add_list_of_reactions = AsyncMock()

        # Step 2 - Call the function
        await discord_env.emoji.emoji_commands(
            discord_env.context, "abcde", True, "Fake discord user"
        )

        # Step 3 - Assert that everything works
        auxiliary.add_list_of_reactions.assert_called_once_with(
            message=discord_env.message_person1_noprefix_1, reactions=["1", "2"]
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)
