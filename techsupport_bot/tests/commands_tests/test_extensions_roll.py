"""
This is a file to test the extensions/roll.py file
This contains 3 tests
"""

from __future__ import annotations

import importlib
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from commands import roll
from core import auxiliary
from hypothesis import given
from hypothesis.strategies import integers
from tests import config_for_tests, helpers


def setup_local_extension(bot: helpers.MockBot = None) -> roll.Roller:
    """A simple function to setup an instance of the roll extension

    Args:
        bot (helpers.MockBot, optional): A fake bot object. Should be used if using a
            fake_discord_env in the test. Defaults to None.

    Returns:
        roll.Roller: The instance of the Roller class
    """
    with patch("asyncio.create_task", return_value=None):
        return roll.Roller(bot)


class Test_RollCommand:
    """A set of tests to test roll_command"""

    @pytest.mark.asyncio
    async def test_generate_embed(self: Self) -> None:
        """A test to ensure that generate_basic_embed is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        roller = setup_local_extension(discord_env.bot)
        roller.get_roll_number = MagicMock(return_value=5)
        auxiliary.generate_basic_embed = MagicMock()
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await roller.roll_command(ctx=discord_env.context, min_value=1, max_value=10)

        # Step 3 - Assert that everything works
        auxiliary.generate_basic_embed.assert_called_once_with(
            title="RNG Roller",
            description="You rolled a 5",
            color=discord.Color.gold(),
            url=roller.ICON_URL,
        )

        # Step 4 - Cleanup
        importlib.reload(auxiliary)

    @pytest.mark.asyncio
    async def test_roll_calls_send(self: Self) -> None:
        """A test to ensure that ctx.send is called correctly"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        roller = setup_local_extension(discord_env.bot)
        roller.get_roll_number = MagicMock(return_value=5)
        auxiliary.generate_basic_embed = MagicMock(return_value="embed")
        discord_env.context.send = AsyncMock()

        # Step 2 - Call the function
        await roller.roll_command(ctx=discord_env.context, min_value=1, max_value=10)

        # Step 3 - Assert that everything works
        discord_env.context.send.assert_called_once_with(embed="embed")

        # Step 4 - Cleanup
        importlib.reload(auxiliary)


class Test_RandomNumber:
    """A single test to test get_roll_number"""

    @given(integers(), integers())
    def test_random_numbers(self: Self, min_value: int, max_value: int) -> None:
        """A property test to ensure that random number doesn't return anything unexpected

        Args:
            min_value (int): A random int to text roll bounds with
            max_value (int): Another random int to test roll bounds with
        """
        # Step 1 - Setup env
        roller = setup_local_extension()
        if min_value > max_value:
            temp = min_value
            max_value = min_value
            min_value = temp

        # Step 2 - Call the function
        result = roller.get_roll_number(min_value=min_value, max_value=max_value)

        # Step 3 - Assert that everything works
        assert isinstance(result, int)
        assert min_value <= result <= max_value
