"""
This is a file to test the extensions/lenny.py file
This contains 2 tests
"""

from unittest.mock import AsyncMock, patch

import pytest
from extensions import lenny

from . import config_for_tests


def setup_local_extension(bot=None):
    """A simple function to setup an instance of the htd extension

    Args:
        bot (MockBot, optional): A fake bot object. Should be used if using a
        fake_discord_env in the test. Defaults to None.

    Returns:
        HTD: The instance of the htd class
    """
    with patch("asyncio.create_task", return_value=None):
        return lenny.Lenny(bot)


class Test_Lenny:
    """A class to house all tests for lenny"""

    def test_line_length(self):
        """A test to ensure we never exceed the 2000 allowed characters"""
        # Step 1 - Setup env
        lenny_test = setup_local_extension()

        # Step 2 - Call the function
        faces = lenny_test.LENNYS_SELECTION

        # Step 3 - Assert that everything works
        for face in faces:
            assert len(face) <= 2000

    @pytest.mark.asyncio
    async def test_lenny_command(self):
        """A test to ensure that the lenny command calls send"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        lenny_test = setup_local_extension(discord_env.bot)
        discord_env.channel.send = AsyncMock()
        lenny_test.LENNYS_SELECTION = ["test"]

        # Step 2 - Call the function
        await lenny_test.lenny_command(discord_env.channel)

        # Step 3 - Assert that everything works
        discord_env.channel.send.assert_called_once_with(content="test")
