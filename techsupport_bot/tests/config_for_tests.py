"""
This includes config for all unit tests
Currently includes:

A PREFIX variable, to assign the prefix to use for tests
A rand_history strategy, for property tests that need a message history
A FakeDiscordEnv for creating a discord environment 100% out of mock ojects
"""

from __future__ import annotations

import random
from collections.abc import Callable  # pylint: disable=W0611
from typing import Self
from unittest.mock import patch

from commands import Burn, Corrector, Emojis, Greeter, MagicConch
from hypothesis.strategies import (  # pylint: disable=W0611
    SearchStrategy,
    composite,
    integers,
    text,
)

from .helpers import (
    MockAsset,
    MockAttachment,
    MockBot,
    MockChannel,
    MockContext,
    MockMember,
    MockMessage,
    MockReaction,
)

PREFIX = "."


@composite
def rand_history(
    draw: (
        Callable[[SearchStrategy[int, int]], int] | Callable[[SearchStrategy[str]], str]
    )
) -> list[MockMessage]:
    """This is a custom strategy to generate a random message history
    This history, returned as an array, will be 1 to 50 messages of random content
    Some will be by a bot, some will not

    Args:
        draw (Callable[[SearchStrategy[int, int]], int] | Callable[[SearchStrategy[str]], str]):
            The strategy used to generate a random history of message.
            This generates both strings and ints

    Returns:
        list[MockMessage]: The randomly generated list of messages
    """
    hist_length = draw(integers(1, 10))
    final_history = []
    botPerson = MockMember(bot=True)
    nonBot = MockMember(bot=False)
    for _ in range(hist_length):
        temp_author = botPerson
        if bool(random.getrandbits(1)):
            temp_author = nonBot
        message = MockMessage(content=draw(text()), author=temp_author)
        final_history.append(message)
    return final_history


class FakeDiscordEnv:
    """Class to setup the mock discord environment for all the tests"""

    def __init__(self: Self) -> None:
        # bot objects
        self.bot = MockBot()

        # asset objects
        self.asset1 = MockAsset(url="realurl")
        self.asset2 = MockAsset(url="differenturl")

        # member objects
        self.person1 = MockMember(
            bot=False, input_id=1, name="person1", display_avatar=self.asset1
        )
        self.person2 = MockMember(
            bot=False, input_id=2, name="person2", display_avatar=self.asset2
        )
        self.person3_bot = MockMember(
            bot=True, input_id=3, name="bot", display_avatar=self.asset1
        )

        # attachment objects
        self.json_attachment = MockAttachment(filename="json.json")
        self.png_attachment = MockAttachment(filename="png.png")

        # message objects
        self.message_person1_prefix = MockMessage(
            content=f"{PREFIX}message", author=self.person1
        )
        self.message_person1_noprefix_1 = MockMessage(
            content="message", author=self.person1, reactions=[]
        )
        self.message_person1_noprefix_2 = MockMessage(
            content="different message", author=self.person1
        )
        self.message_person2_prefix = MockMessage(
            content=f"{PREFIX}message", author=self.person2
        )
        self.message_person2_noprefix_1 = MockMessage(
            content="message", author=self.person2
        )
        self.message_person2_noprefix_2 = MockMessage(
            content="different message", author=self.person2
        )
        self.message_person2_noprefix_3 = MockMessage(
            content="even different message", author=self.person2
        )
        self.message_person3_noprefix = MockMessage(
            content="bot message", author=self.person3_bot
        )
        self.message_person1_attachments = MockMessage(
            content="Attachments",
            author=self.person1,
            attachments=[self.json_attachment],
        )
        self.message_reaction1 = MockMessage(content="2", reactions=[1])
        self.message_reaction2 = MockMessage(reactions=[0])
        self.message_reaction3 = MockMessage(reactions=[20])

        # channel objects
        self.channel = MockChannel()

        # context objects
        self.context = MockContext(channel=self.channel, author=self.person1)

        # extension objects.
        # Since these all call setup, we remove async create task when creating them
        with patch("asyncio.create_task", return_value=None):
            self.burn = Burn(self.bot)
            self.correct = Corrector(self.bot)
            self.conch = MagicConch(self.bot)
            self.emoji = Emojis(self.bot)
            self.hello = Greeter(self.bot)

        # reaction objects.
        self.reaction1 = MockReaction(message="2", count=1)
        self.reaction2 = MockReaction(count=0)
