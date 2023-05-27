"""Module for defining custom contexts.
"""

import asyncio

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

    def task_paginate(self, pages: list):
        """Creates a pagination task from the given args.

        This is useful if you want your command to finish executing when pagination starts.
        """
        pagination_view = PaginateView()
        pagination_view.data = pages
        asyncio.create_task(pagination_view.send(ctx=self))

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


class PaginateView(discord.ui.View):
    """The custom paginate view class
    This holds all the buttons and how the pages should work
    """

    current_page: int = 1
    data = None
    currCtx = None
    timeout = 120
    message = ""

    def add_page_numbers(self):
        """A simple function to add page numbers to embed footer"""
        for index, embed in enumerate(self.data):
            if isinstance(embed, discord.Embed):
                embed.set_footer(text=f"Page {index+1} of {len(self.data)}")

    async def send(self, ctx):
        """The initial send function. This does any one time actions and sends page 1"""
        self.currCtx = ctx
        self.update_buttons()
        if isinstance(self.data[0], discord.Embed):
            self.add_page_numbers()
        self.message = await ctx.send(view=self)
        if len(self.data) == 1:
            self.remove_item(self.prev_button)
            self.remove_item(self.next_button)
        await self.update_message()

    async def update_message(self):
        """The redraws the message with the new page"""
        self.update_buttons()
        if isinstance(self.data[self.current_page - 1], discord.Embed):
            await self.message.edit(embed=self.data[self.current_page - 1], view=self)
        else:
            await self.message.edit(content=self.data[self.current_page - 1], view=self)

    def update_buttons(self):
        """This disables buttons if there are no more pages forward/backward"""
        if self.current_page == 1:
            self.prev_button.disabled = True
            self.prev_button.style = discord.ButtonStyle.gray
        else:
            self.prev_button.disabled = False
            self.prev_button.style = discord.ButtonStyle.primary

        if self.current_page == len(self.data):
            self.next_button.disabled = True
            self.next_button.style = discord.ButtonStyle.gray
        else:
            self.next_button.disabled = False
            self.next_button.style = discord.ButtonStyle.primary

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary, row=1)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """This declares the previous button, and what should happen when it's pressed"""
        await interaction.response.defer()
        self.current_page -= 1
        await self.update_message()

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary, row=1)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """This declares the next button, and what should happen when it's pressed"""
        await interaction.response.defer()
        self.current_page += 1
        await self.update_message()

    @discord.ui.button(emoji="🛑", style=discord.ButtonStyle.danger, row=1)
    async def stop_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        """This declares the stop button, and what should happen when it's pressed"""
        await interaction.response.defer()
        self.clear_items()
        await self.update_message()

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def trash_button(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        """This declares the trash button, and what should happen when it's pressed"""
        await interaction.response.defer()
        await self.message.delete()

    async def interaction_check(self, interaction):
        """This checks to ensure that only the original author can press the button
        If the original author didn't press, it sends an ephemeral message
        """
        if interaction.user != self.currCtx.author:
            await interaction.response.send_message(
                "Only the original author can control this!", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """This deletes the buttons after the 60 second timeout has elapsed"""
        self.clear_items()
        await self.update_message()
