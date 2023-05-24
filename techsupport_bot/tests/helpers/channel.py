class MockChannel:
    def __init__(self, history=None):
        self.message_history = history

    async def history(self, limit):
        for message in self.message_history:
            yield message
