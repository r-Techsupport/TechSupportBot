"""
This is a file to test the extensions/emoji.py file
This contains 14 tests
"""


from unittest.mock import AsyncMock, MagicMock

import mock
import pytest
from base import auxiliary

from . import config_for_tests


class Test_EmojiFromChar:
    """A class to test the emoji_from_char method"""

    @mock.patch("asyncio.create_task", return_value=None)
    def test_lowercase_letter(self, _):
        """A test to ensure that a lowercase letter returns correctly"""
        discord_env = config_for_tests.FakeDiscordEnv()
        char = discord_env.emoji.emoji_from_char("a")
        assert char == "🇦"

    @mock.patch("asyncio.create_task", return_value=None)
    def test_uppercase_letter(self, _):
        """A test to ensure that a uppsercase letter returns correctly"""
        discord_env = config_for_tests.FakeDiscordEnv()
        char = discord_env.emoji.emoji_from_char("A")
        assert char == "🇦"

    @mock.patch("asyncio.create_task", return_value=None)
    def test_number(self, _):
        """A test to ensure that a number returns correctly"""
        discord_env = config_for_tests.FakeDiscordEnv()
        char = discord_env.emoji.emoji_from_char("1")
        assert char == "1️⃣"

    @mock.patch("asyncio.create_task", return_value=None)
    def test_question_mark(self, _):
        """A test to ensure that a uppsercase letter returns correctly"""
        discord_env = config_for_tests.FakeDiscordEnv()
        char = discord_env.emoji.emoji_from_char("?")
        assert char == "❓"

    @mock.patch("asyncio.create_task", return_value=None)
    def test_invalid(self, _):
        """A test to ensure that a uppsercase letter returns correctly"""
        discord_env = config_for_tests.FakeDiscordEnv()
        char = discord_env.emoji.emoji_from_char("]")
        assert char is None


class Test_CheckIfAllUnique:
    """A class to test the check_if_all_unique method"""

    @mock.patch("asyncio.create_task", return_value=None)
    def test_unique(self, _):
        """Test to ensure that a unique string is detected"""
        discord_env = config_for_tests.FakeDiscordEnv()
        response = discord_env.emoji.check_if_all_unique("abcde")
        assert response

    @mock.patch("asyncio.create_task", return_value=None)
    def test_non_unique(self, _):
        """Test to ensure that a non-unique string is detected"""
        discord_env = config_for_tests.FakeDiscordEnv()
        response = discord_env.emoji.check_if_all_unique("abcade")
        assert not response


class Test_GenerateEmojiString:
    """A class to test the generate_emoji_string method"""

    @mock.patch("asyncio.create_task", return_value=None)
    def test_only_emoji(self, _):
        """Test to ensure that only_emoji works when true"""
        discord_env = config_for_tests.FakeDiscordEnv()
        response = discord_env.emoji.generate_emoji_string("abcd!@#$1234", True)
        assert len(response) == 9
        assert response == ["🇦", "🇧", "🇨", "🇩", "❗", "1️⃣", "2️⃣", "3️⃣", "4️⃣"]

    @mock.patch("asyncio.create_task", return_value=None)
    def test_non_emoji(self, _):
        """Test to ensure that only_emoji works when false"""
        discord_env = config_for_tests.FakeDiscordEnv()
        response = discord_env.emoji.generate_emoji_string("abcd!@#$1234", False)
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
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_empty_string(self, _):
        """Test to ensure that an error is thrown on a empty response"""
        discord_env = config_for_tests.FakeDiscordEnv()

        discord_env.emoji.generate_emoji_string = MagicMock(return_value=[])
        discord_env.context.send_deny_embed = AsyncMock()

        await discord_env.emoji.emoji_commands(discord_env.context, "abcde", False)

        discord_env.context.send_deny_embed.assert_called_once_with(
            "I can't get any emoji letters from your message!"
        )

    @pytest.mark.asyncio
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_find_no_message(self, _):
        """Test to ensure that if no message could be found, an error will occur"""
        discord_env = config_for_tests.FakeDiscordEnv()

        discord_env.emoji.generate_emoji_string = MagicMock(return_value=["1"])
        auxiliary.search_channel_for_message = AsyncMock(return_value=None)

        discord_env.context.send_deny_embed = AsyncMock()

        await discord_env.emoji.emoji_commands(
            discord_env.context, "abcde", False, "Fake discord user"
        )

        discord_env.context.send_deny_embed.assert_called_once_with(
            "No valid messages found to react to!"
        )

    @pytest.mark.asyncio
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_unique_error(self, _):
        """Test to ensure that if the string is not unique, an error will occur"""
        discord_env = config_for_tests.FakeDiscordEnv()

        discord_env.emoji.generate_emoji_string = MagicMock(return_value=["1"])
        discord_env.emoji.check_if_all_unique = MagicMock(return_value=False)

        discord_env.context.send_deny_embed = AsyncMock()

        await discord_env.emoji.emoji_commands(discord_env.context, "abcde", True)

        discord_env.context.send_deny_embed.assert_called_once_with(
            "Invalid message! Make sure there are no repeat characters!"
        )

    @pytest.mark.asyncio
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_confirm_with_proper_call(self, _):
        """Test that send_confirm_embed is being called with the proper string"""
        discord_env = config_for_tests.FakeDiscordEnv()

        discord_env.emoji.generate_emoji_string = MagicMock(return_value=["1", "2"])

        discord_env.context.send_confirm_embed = AsyncMock()

        await discord_env.emoji.emoji_commands(discord_env.context, "abcde", False)

        discord_env.context.send_confirm_embed.assert_called_once_with("1 2")

    @pytest.mark.asyncio
    @mock.patch("asyncio.create_task", return_value=None)
    async def test_proper_reactions(self, _):
        """Test that send_confirm_embed is being called with the proper string"""
        discord_env = config_for_tests.FakeDiscordEnv()

        discord_env.emoji.generate_emoji_string = MagicMock(return_value=["1", "2"])

        auxiliary.search_channel_for_message = AsyncMock(
            return_value=discord_env.message_person1_noprefix_1
        )
        auxiliary.add_list_of_reactions = AsyncMock()

        await discord_env.emoji.emoji_commands(
            discord_env.context, "abcde", True, "Fake discord user"
        )

        auxiliary.add_list_of_reactions.assert_called_once_with(
            message=discord_env.message_person1_noprefix_1, reactions=["1", "2"]
        )
