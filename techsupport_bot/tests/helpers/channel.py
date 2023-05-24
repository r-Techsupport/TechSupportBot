"""
This is a file to store the fake disord.TextChannel objection
"""


class MockChannel:
    """
    This is the MockChannel class

    Currently implemented variables and methods:
    message_history -> A list of MockMessage objects
    history() -> An async function to return history.
        A "limit" object may be passed, but is ignored in this implementation
    """

    def __init__(self, history=None):
        self.message_history = history

    async def history(self, limit):
        for message in self.message_history:
            yield message
