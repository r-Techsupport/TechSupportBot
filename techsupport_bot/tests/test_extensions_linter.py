"""
This is a file to test the extensions/linter.py file
This contains 9 tests
"""

import importlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import util
from base import auxiliary
from extensions import linter

from . import config_for_tests


def setup_local_extension(bot=None):
    """A simple function to setup an instance of the linter extension

    Args:
        bot (MockBot, optional): A fake bot object. Should be used if using a
        fake_discord_env in the test. Defaults to None.

    Returns:
        Lint: The instance of the Lint class
    """
    with patch("asyncio.create_task", return_value=None):
        return linter.Lint(bot)


class Test_CheckSyntax:
    """A set of tests to test check_syntax"""

    @pytest.mark.asyncio
    async def test_no_error(self):
        """A test to ensure that nothing is retuend when there is no error"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)
        util.get_json_from_attachments = AsyncMock()

        # Step 2 - Call the function
        result = await linter_test.check_syntax(discord_env.message_person1_attachments)

        # Step 3 - Assert that everything works
        assert result is None

    @pytest.mark.asyncio
    async def test_yes_error(self):
        """A test to ensure that something is returned when there is an error"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)
        util.get_json_from_attachments = AsyncMock(
            side_effect=json.JSONDecodeError("1", "1", 1)
        )

        # Step 2 - Call the function
        result = await linter_test.check_syntax(discord_env.message_person1_attachments)

        # Step 3 - Assert that everything works
        assert result is not None


class Test_LintCommand:
    """A set of tests to set lint_command"""

    @pytest.mark.asyncio
    async def test_failed_valid_attachments(self):
        """A test to ensure deny embed is called when invalid attachments"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)
        auxiliary.send_deny_embed = AsyncMock()
        linter_test.check_valid_attachments = MagicMock(return_value=False)
        discord_env.context.message = discord_env.message_person1_attachments

        # Step 2 - Call the function
        await linter_test.lint_command(discord_env.context)

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="You need to attach a single .json file",
            channel=discord_env.context.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_failed_check_syntax(self):
        """A test to ensure deny embed is called when invalid attachments"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)
        auxiliary.send_deny_embed = AsyncMock()
        linter_test.check_valid_attachments = MagicMock(return_value=True)
        linter_test.check_syntax = AsyncMock(return_value="error")
        discord_env.context.message = discord_env.message_person1_attachments

        # Step 2 - Call the function
        await linter_test.lint_command(discord_env.context)

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="Invalid syntax!\nError thrown: `error`",
            channel=discord_env.context.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_success(self):
        """A test to ensure confirm embed is called if everything is good"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)
        auxiliary.send_confirm_embed = AsyncMock()
        linter_test.check_valid_attachments = MagicMock(return_value=True)
        linter_test.check_syntax = AsyncMock(return_value=None)
        discord_env.context.message = discord_env.message_person1_attachments

        # Step 2 - Call the function
        await linter_test.lint_command(discord_env.context)

        # Step 3 - Assert that everything works
        auxiliary.send_confirm_embed.assert_called_once_with(
            message="Syntax is OK",
            channel=discord_env.context.channel,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)


class Test_CheckAttachments:
    """A set of tests to test check_valid_attachments"""

    def test_no_attachments(self):
        """A test to ensure that False is returned if run without attachments"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = linter_test.check_valid_attachments([])

        # Step 3 - Assert that everything works
        assert not result

    def test_two_attachments(self):
        """A test to ensure that False is returned if run with more than 1 attachment"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = linter_test.check_valid_attachments(
            [discord_env.json_attachment, discord_env.json_attachment]
        )

        # Step 3 - Assert that everything works
        assert not result

    def test_non_json(self):
        """A test to ensure that False is returned if run without json attachments"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = linter_test.check_valid_attachments([discord_env.png_attachment])

        # Step 3 - Assert that everything works
        assert not result

    def test_one_json(self):
        """A test to ensure that True is returned if run with 1 json attachment"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        linter_test = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = linter_test.check_valid_attachments([discord_env.json_attachment])

        # Step 3 - Assert that everything works
        assert result
