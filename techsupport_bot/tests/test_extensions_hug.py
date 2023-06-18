"""
This is a file to test the extensions/hug.py file
This contains 3 tests
"""

from unittest.mock import AsyncMock, MagicMock, call, patch

import discord
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

    @pytest.mark.asyncio
    async def test_eligible(self):
        """A test to ensure that when 2 different members are passed, True is returned"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hugger = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = await hugger.check_hug_eligibility(
            author=discord_env.person1,
            user_to_hug=discord_env.person2,
            channel=discord_env.channel,
        )

        # Step 3 - Assert that everything works
        assert result == True

    @pytest.mark.asyncio
    async def test_ineligible(self):
        """A test to ensure that when the same person is passed twice, False is returned"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        hugger = setup_local_extension(discord_env.bot)

        # Step 2 - Call the function
        result = await hugger.check_hug_eligibility(
            author=discord_env.person1,
            user_to_hug=discord_env.person1,
            channel=discord_env.channel,
        )

        # Step 3 - Assert that everything works
        assert result == False


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


