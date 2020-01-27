"""Module for base cogs.
"""

from discord.ext import commands

from logger import get_logger

log = get_logger("Cogs")


class BasicPlugin(commands.Cog):
    """The base plugin class.

    parameters:
        bot (Bot): the bot object
    """

    def __init__(self, bot):
        self.bot = bot


class MatchPlugin(BasicPlugin):
    """Plugin for matching a message.
    """

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listens for a message and passes it to the response handler if valid.

        parameters:
            message (message): the message object
        """
        if message.author == self.bot.user:
            return

        ctx = await self.bot.get_context(message)

        try:
            if self.match(message.content):
                await self.response(ctx, message.content)
        except Exception as e:
            log.exception(e)

    def match(self, content):
        """Runs a boolean check on message content.

        parameters:
            content (str): the message content
        """
        raise RuntimeError("Match function must be defined in sub-class")

    async def response(self, ctx, content):
        """Performs a response if the match is valid.

        parameters:
            ctx (context): the context object
            content (str): the message content
        """
        raise RuntimeError("Response function must be defined in sub-class")
