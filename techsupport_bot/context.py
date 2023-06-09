"""Module for defining custom contexts.
"""

import embeds
from discord.ext import commands


class Context(commands.Context):
    """Custom context object to provide more functionality."""

    def construct_mention_string(self, targets):
        """Builds a string of mentions from a list of users.

        parameters:
            targets ([]discord.User): the list of users to mention
        """
        constructed = set()

        # construct mention string
        user_mentions = ""
        for index, target in enumerate(targets):
            mid = getattr(target, "id", 0)
            if mid in constructed:
                continue

            mention = getattr(target, "mention", None)
            if not mention:
                continue

            constructed.add(mid)

            spacer = " " if (index != len(targets) - 1) else ""
            user_mentions += mention + spacer

        return user_mentions

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

        mention_string = self.construct_mention_string(targets)
        if mention_string:
            provided_content = kwargs.get("content") or ""
            kwargs["content"] = f"{mention_string} {provided_content}"

        message = await super().send(*args, **kwargs)
        return message

    async def send_confirm_embed(self, content, targets=None):
        """Sends a confirmation embed.

        parameters:
            content (str): the base confirmation message
            targets ([]discord.User): the list of users to mention
        """
        embed = embeds.ConfirmEmbed(message=content)
        message = await self.send(embed=embed, targets=targets or [])
        return message

    async def send_deny_embed(self, content, targets=None):
        """Sends a deny embed.

        parameters:
            content (str): the base confirmation message
            targets ([]discord.User): the list of users to mention
        """
        embed = embeds.DenyEmbed(message=content)
        message = await self.send(embed=embed, targets=targets or [])
        return message
