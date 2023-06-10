"""Module for defining custom contexts.
"""


import discord
import embeds
from discord.ext import commands


class Context(commands.Context):
    """Custom context object to provide more functionality."""

    CONFIRM_YES_EMOJI = "✅"
    CONFIRM_NO_EMOJI = "❌"

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

    async def confirm(self, message, timeout=60, delete_after=True, bypass=None):
        """Waits on a confirm reaction from a given user.

        parameters:
            message (str): the message content to which the user reacts
            timeout (int): the number of seconds before timing out
            delete_after (bool): True if the confirmation message should be deleted
            bypass (list[discord.Role]): the list of roles able to confirm (empty by default)
        """
        if bypass is None:
            bypass = []

        embed = discord.Embed(title="Please confirm!", description=message)
        embed.color = discord.Color.green()

        message = await self.send(embed=embed)
        await message.add_reaction(self.CONFIRM_YES_EMOJI)
        await message.add_reaction(self.CONFIRM_NO_EMOJI)

        result = False
        while True:
            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add",
                    timeout=timeout,
                    check=lambda r, u: not bool(u.bot) and r.message.id == message.id,
                )
            except Exception:
                break

            member = self.guild.get_member(user.id)
            if not member:
                pass

            elif user.id != self.author.id and not any(
                role in getattr(member, "roles", []) for role in bypass
            ):
                pass

            elif str(reaction) == self.CONFIRM_YES_EMOJI:
                result = True
                break

            elif str(reaction) == self.CONFIRM_NO_EMOJI:
                break

            try:
                await reaction.remove(user)
            except discord.Forbidden:
                pass

        if delete_after:
            await message.delete()

        return result
