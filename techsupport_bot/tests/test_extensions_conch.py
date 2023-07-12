"""
This is a file to test the extensions/conch.py file
This contains 3 tests
"""

from hypothesis import given
from hypothesis.strategies import text

from . import config_for_tests


class Test_FormatQuestion:
    """Tests to test the format_question function"""

    @given(text())
    def test_format_question(self, question):
        """Property test to ensure the question is cropped correcty, never altered,
        and always ends in a question mark"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_question = discord_env.conch.format_question(question)

        # Step 3 - Assert that everything works
        assert new_question.endswith("?")
        assert len(new_question) <= 256
        assert new_question[:-1] in question
        assert len(question) >= len(new_question) - 1

    def test_format_question_no_mark(self):
        """Test to ensure that format question adds a question mark if needed"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_question = discord_env.conch.format_question("This is a question")

        # Step 3 - Assert that everything works
        assert new_question == "This is a question?"

    def test_format_question_yes_mark(self):
        """Test to ensure that the format question doesn't add a
        question mark when the question ends with a question mark"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()

        # Step 2 - Call the function
        new_question = discord_env.conch.format_question("This is a question?")

        # Step 3 - Assert that everything works
        assert new_question == "This is a question?"
