"""
This is a file to test the extensions/conch.py file
This contains 3 tests
"""

import mock
from hypothesis import given
from hypothesis.strategies import text

from . import config_for_tests


class Test_FormatQuestion:
    """Tests to test the format_question function"""

    @given(text())
    def test_format_question(self, question):
        """Property test to ensure the question is cropped correcty, never altered,
        and always ends in a question mark"""
        with mock.patch("asyncio.create_task", return_value=None):
            discord_env = config_for_tests.FakeDiscordEnv()
            new_question = discord_env.conch.format_question(question)
            assert new_question.endswith("?")
            assert len(new_question) <= 256
            assert new_question[:-1] in question
            assert len(question) >= len(new_question) - 1

    @mock.patch("asyncio.create_task", return_value=None)
    def test_format_question_no_mark(self, _):
        """Test to ensure that format question adds a question mark if needed"""
        discord_env = config_for_tests.FakeDiscordEnv()
        new_question = discord_env.conch.format_question("This is a question")
        assert new_question == "This is a question?"

    @mock.patch("asyncio.create_task", return_value=None)
    def test_format_question_yes_mark(self, _):
        """Test to ensure that the format question doesn't add a
        question mark when the question ends with a question mark"""
        discord_env = config_for_tests.FakeDiscordEnv()
        new_question = discord_env.conch.format_question("This is a question?")
        assert new_question == "This is a question?"
