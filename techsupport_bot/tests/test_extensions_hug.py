"""
This is a file to test the extensions/hug.py file
This contains 5 tests
"""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from base import auxiliary
from extensions import hug

from . import config_for_tests


def setup_local_extension(bot=None):
    """A simple function to setup an instance of the hug extension

    Args:
        bot (MockBot, optional): A fake bot object. Should be used if using a
        fake_discord_env in the test. Defaults to None.

    Returns:
        Hugger: The instance of the Hugger class
    """
    with patch("asyncio.create_task", return_value=None):
        return hug.Hugger(bot)


class Test_CheckEligibility:
    """A set of tests to test split_nicely"""

    def test_eligible(self):
        """A test to ensure that when 2 different members are passed, True is returned"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hugger = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = hugger.check_hug_eligibility(
            author=discord_env.person1, user_to_hug=discord_env.person2
        )

        # Step 3 - Assert that everything works
        assert result is True

    def test_ineligible(self):
        """A test to ensure that when the same person is passed twice, False is returned"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hugger = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = hugger.check_hug_eligibility(
            author=discord_env.person1, user_to_hug=discord_env.person1
        )

        # Step 3 - Assert that everything works
        assert result is False


class Test_GeneratePhrase:
    """A set of tests to test generate_hug_phrase"""

    def test_string_generation(self):
        """A test to ensure that string generation is working correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hugger = setup_local_extension(discord_env.bot)
        hugger.HUGS_SELECTION = ["{user_giving_hug} squeezes {user_to_hug} to death"]

        # Step 2 - Call the function
        output = hugger.generate_hug_phrase(
            author=discord_env.person1, user_to_hug=discord_env.person2
        )

        # Step 3 - Assert that everything works
        assert output == "<@1> squeezes <@2> to death"


class Test_HugCommand:
    """A set of tests to test hug_command"""

    @pytest.mark.asyncio
    async def test_failure(self):
        """A test to ensure that nothing is called when the eligiblity is False"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hugger = setup_local_extension(discord_env.bot)
        hugger.check_hug_eligibility = MagicMock(return_value=False)
        auxiliary.send_deny_embed = AsyncMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hugger.hug_command(discord_env.context, discord_env.person2)

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_called_once_with(
            message="Let's be serious",
            channel=discord_env.context.channel,
        )
        discord_env.context.send.assert_not_called()

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_success(self):
        """A test to ensure that send is properly called"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hugger = setup_local_extension(discord_env.bot)
        hugger.check_hug_eligibility = MagicMock(return_value=True)
        hugger.generate_hug_phrase = MagicMock()
        auxiliary.send_deny_embed = AsyncMock()
        auxiliary.generate_basic_embed = MagicMock(return_value="Embed")
        auxiliary.construct_mention_string = MagicMock(return_value="String")
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await hugger.hug_command(discord_env.context, discord_env.person2)

        # Step 3 - Assert that everything works
        auxiliary.send_deny_embed.assert_not_called()
        discord_env.context.send.assert_called_once_with(
            embed="Embed", content="String"
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)
