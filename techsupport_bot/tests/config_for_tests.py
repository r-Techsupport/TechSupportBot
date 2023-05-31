"""
This includes config for all unit tests
Currently includes:

A PREFIX variable, to assign the prefix to use for tests
A rand_history strategy, for property tests that need a message history
A FakeDiscordEnv for creating a discord environment 100% out of mock ojects
"""

import random

from extensions import Burn, Corrector, MagicConch
from hypothesis.strategies import composite, integers, text

from .helpers import MockBot, MockChannel, MockContext, MockMember, MockMessage

PREFIX = "."


@composite
def rand_history(draw):
    """This is a custom strategy to generate a random message history
    This history, returned as an array, will be 1 to 50 messages of random content
    Some will be by a bot, some will not
    """
    hist_length = draw(integers(1, 50))
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

    def __init__(self):
        # bot objects
        self.bot = MockBot()

        # member objects
        self.person1 = MockMember(bot=False, id=1)
        self.person2 = MockMember(bot=False, id=2)
        self.person3_bot = MockMember(bot=True, id=3)

        # message objects
        self.message_person1_prefix = MockMessage(
            content=f"{PREFIX}message", author=self.person1
        )
        self.message_person1_noprefix_1 = MockMessage(
            content="message", author=self.person1
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

        # channel objects
        self.channel = MockChannel()

        # context objects
        self.context = MockContext(channel=self.channel)

        # extension objects
        self.burn = Burn(self.bot)
        self.correct = Corrector(self.bot)
        self.conch = MagicConch(self.bot)
