"""Module for defining custom contexts.
"""

import datetime

import discord
import embeds
from discord.ext import commands


class Context(commands.Context):
    """Custom context object to provide more functionality."""

    CONFIRM_YES_EMOJI = "✅"
    CONFIRM_NO_EMOJI = "❌"
    PAGINATE_LEFT_EMOJI = "⬅️"
    PAGINATE_RIGHT_EMOJI = "➡️"
    PAGINATE_STOP_EMOJI = "⏹️"
    PAGINATE_DELETE_EMOJI = "🗑️"

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

    # pylint: disable=too-many-branches, too-many-arguments
    async def paginate(self, pages, timeout=300):
        """Paginates a set of embed objects for users to sort through

        parameters:
            pages (Union[discord.Embed, str][]): the pages (or URLs to render them) to paginate
            timeout (int) (seconds): the time to wait before exiting the reaction listener
        """
        # limit large outputs
        pages = pages[:20]

        for index, embed in enumerate(pages):
            if isinstance(embed, discord.Embed):
                embed.set_footer(text=f"Page {index+1} of {len(pages)}")

        index = 0
        get_args = lambda index: {
            "content": pages[index]
            if not isinstance(pages[index], discord.Embed)
            else None,
            "embed": pages[index] if isinstance(pages[index], discord.Embed) else None,
        }

        message = await self.send(**get_args(index))

        if isinstance(self.channel, discord.DMChannel):
            return

        start_time = datetime.datetime.now()

        for unicode_reaction in [
            self.PAGINATE_LEFT_EMOJI,
            self.PAGINATE_RIGHT_EMOJI,
            self.PAGINATE_STOP_EMOJI,
            self.PAGINATE_DELETE_EMOJI,
        ]:
            await message.add_reaction(unicode_reaction)

        while True:
            if (datetime.datetime.now() - start_time).seconds > timeout:
                break

            try:
                reaction, user = await self.bot.wait_for(
                    "reaction_add",
                    timeout=timeout,
                    check=lambda r, u: not bool(u.bot) and r.message.id == message.id,
                )
            # this seems to raise an odd timeout error, for now just catch-all
            except Exception:
                break

            if user.id != self.author.id:
                # this is checked first so it can pass to the deletion
                pass

            # move forward
            elif str(reaction) == self.PAGINATE_RIGHT_EMOJI and index < len(pages) - 1:
                index += 1
                await message.edit(**get_args(index))

            # move backward
            elif str(reaction) == self.PAGINATE_LEFT_EMOJI and index > 0:
                index -= 1
                await message.edit(**get_args(index))

            # stop pagination
            elif str(reaction) == self.PAGINATE_STOP_EMOJI:
                break

            # delete embed
            elif str(reaction) == self.PAGINATE_DELETE_EMOJI:
                await message.delete()
                break

            try:
                await reaction.remove(user)
            except discord.Forbidden:
                pass

        try:
            await message.clear_reactions()
        except discord.NotFound:
            pass

    def task_paginate(self, *args, **kwargs):
        """Creates a pagination task from the given args.

        This is useful if you want your command to finish executing when pagination starts.
        """
        self.bot.loop.create_task(self.paginate(*args, **kwargs))

    async def confirm(self, message, timeout=60, delete_after=False, bypass=None):
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
