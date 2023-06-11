"""
This is a file to test the extensions/hello.py file
This contains 1 test
"""


from unittest.mock import AsyncMock

import pytest
from base import auxiliary

from . import config_for_tests


class Test_Hello:
    """A single test to test the hello command"""

    @pytest.mark.asyncio
    async def test_hello_command(self):
        """This is a test to ensure that the proper reactions are called,
        and in the proper order"""
        # Step 1 - Setup env
        discord_env = config_for_tests.FakeDiscordEnv()
        auxiliary.add_list_of_reactions = AsyncMock()
        discord_env.context.message = discord_env.message_person1_noprefix_1

        # Step 2 - Call the function
        await discord_env.hello.hello_command(discord_env.context)

        # Step 3 - Assert that everything works
        auxiliary.add_list_of_reactions.assert_called_once_with(
            message=discord_env.message_person1_noprefix_1, reactions=["🇭", "🇪", "🇾"]
        )
