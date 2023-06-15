"""Module for defining custom contexts.
"""

from base import auxiliary
from discord.ext import commands


class Context(commands.Context):
    """Custom context object to provide more functionality."""

    async def send(self, *args, **kwargs):
        """Wraps the parent send with a targets argument to allow mentioning.

        parameters:
            mention_author (bool): True if the author should be mentioned
            targets ([]discord.User): the list of users to mention
        """
        targets = kwargs.pop("targets", [])
        if targets is None:
            targets = []

        # default to mentioning the author
        mention_author = kwargs.pop("mention_author", True)
        if mention_author:
            targets.insert(0, self.author)

        mention_string = auxiliary.construct_mention_string(targets)
        if mention_string:
            provided_content = kwargs.get("content") or ""
            kwargs["content"] = f"{mention_string} {provided_content}"

        message = await super().send(*args, **kwargs)
        return message
