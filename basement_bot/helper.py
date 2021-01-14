"""Provides an interface for accessing common helper methods.
"""

import ast
import datetime
import re

import munch
from api import BotAPI
from discord import Forbidden, NotFound
from discord.channel import DMChannel
from discord.errors import HTTPException


class HelperAPI(BotAPI):
    """API for helper functions.

    parameters:
        bot (BasementBot): the bot object
    """

    def __init__(self, bot):
        super().__init__(bot)
        # provides a simpler interface
        self.bot.h = self

    async def tagged_response(self, ctx, content=None, embed=None, target=None):
        """Sends a context response with the original author tagged.

        parameters:
            ctx (Context): the context object
            message (str): the message to send
            embed (discord.Embed): the discord embed object to send
            target (discord.Member): the Discord user to tag
        """
        who_to_tag = target.mention if target else ctx.message.author.mention
        content = f"{who_to_tag} {content}" if content else who_to_tag
        try:
            message = await ctx.send(content, embed=embed)
        except HTTPException:
            message = None
        return message

    async def priv_response(self, ctx, content=None, embed=None, target=None):
        """Sends a context private message to the original author.

        parameters:
            ctx (Context): the context object
            message (str): the message to send
            embed (discord.Embed): the discord embed object to send
        """
        who_to_dm = target or ctx.author
        try:
            if content:
                message = await who_to_dm.send(content, embed=embed)
            else:
                message = await who_to_dm.send(embed=embed)
        except (Forbidden, HTTPException):
            message = None
        return message

    async def emoji_reaction(self, ctx, emojis):
        """Adds an emoji reaction to the given context message.

        parameters:
            ctx (Context): the context object
            emojis (list, string): the set of (or single) emoji(s) in unicode format
        """
        if not isinstance(emojis, list):
            emojis = [emojis]

        for emoji in emojis:
            try:
                await ctx.message.add_reaction(emoji)
            except Forbidden:
                pass

    def get_guild_from_channel_id(self, channel_id):
        """Helper for getting the guild associated with a channel.

        parameters:
            bot (BasementBot): the bot object
            channel_id (Union[string, int]): the unique ID of the channel
        """
        for guild in self.bot.guilds:
            for channel in guild.channels:
                if channel.id == int(channel_id):
                    return guild
        return None

    def embed_from_kwargs(self, title=None, description=None, **kwargs):
        """Wrapper for generating an embed from a set of key, values.

        parameters:
            title (str): the title for the embed
            description (str): the description for the embed
            **kwargs (dict): a set of keyword values to be displayed
        """
        embed = self.bot.embed_api.Embed(title=title, description=description)
        for key, value in kwargs.items():
            embed.add_field(name=key, value=value, inline=False)
        return embed

    def sub_mentions_for_usernames(self, content):
        """Subs a string of Discord mentions with the corresponding usernames.

        parameters:
            bot (BasementBot): the bot object
            content (str): the content to parse
        """

        def get_nick_from_id_match(match):
            id_ = int(match.group(1))
            user = self.bot.get_user(id_)
            return f"@{user.name}" if user else "@user"

        return re.sub(r"<@?!?(\d+)>", get_nick_from_id_match, content)

    # pylint: disable=too-many-arguments
    async def delete_message_with_reason(
        self, message, reason, private=True, original=True
    ):
        """Deletes a message and provides a reason to the user.

        parameters:
            message (Message): the message object
            reason (str): the reason to provide for deletion
            private (bool): True if the reason should be private messaged
            original (bool): True if the user should be provided the original message
        """
        content = message.content
        send_object = message.author if private else message.channel

        await message.delete()

        await send_object.send(f"Your message was deleted because: `{reason}`")

        if original:
            await send_object.send(f"Original message: ```{content}```")

    async def get_json_from_attachment(
        self, ctx, message, send_msg_on_none=True, send_msg_on_failure=True
    ):
        """Returns a JSON object parsed from a message's attachment.

        parameters:
            message (Message): the message object
            send_msg_on_none (bool): True if a message should be DM'd when no attachments are found
            send_msg_on_failure (bool): True if a message should be DM'd when JSON is invalid
        """
        if not message.attachments:
            if send_msg_on_none:
                await self.priv_response(
                    ctx, "I couldn't find any message attachments!"
                )
            return None

        try:
            json_bytes = await message.attachments[0].read()
            json_str = json_bytes.decode("UTF-8")
            # hehehe munch ~~O< oooo
            return munch.munchify(ast.literal_eval(json_str))
        # this could probably be more specific
        except Exception as e:
            if send_msg_on_failure:
                await self.priv_response(ctx, f"I was unable to parse your JSON: {e}")
            return {}

    # pylint: disable=too-many-branches, too-many-arguments
    async def paginate(self, ctx, embeds, timeout=300, tag_user=False, restrict=False):
        """Paginates a set of embed objects for users to sort through

        parameters:
            ctx (Context): the context object for the message
            embeds (Union[discord.Embed, str][]): the embeds (or URLs to render them) to paginate
            timeout (int) (seconds): the time to wait before exiting the reaction listener
            tag_user (bool): True if the context user should be mentioned in the response
            restrict (bool): True if only the caller and admins can navigate the pages
        """
        # limit large outputs
        embeds = embeds[:10]

        for index, embed in enumerate(embeds):
            if isinstance(embed, self.bot.embed_api.Embed):
                embed.set_footer(text=f"Page {index+1} of {len(embeds)}")

        index = 0
        get_args = lambda index: {
            "content": embeds[index]
            if not isinstance(embeds[index], self.bot.embed_api.Embed)
            else None,
            "embed": embeds[index]
            if isinstance(embeds[index], self.bot.embed_api.Embed)
            else None,
        }

        if tag_user:
            message = await self.tagged_response(ctx, **get_args(index))
        else:
            message = await ctx.send(**get_args(index))

        if isinstance(ctx.channel, DMChannel):
            return

        start_time = datetime.datetime.now()

        for unicode_reaction in ["\u25C0", "\u25B6", "\u26D4", "\U0001F5D1"]:
            await message.add_reaction(unicode_reaction)

        while True:
            if (datetime.datetime.now() - start_time).seconds > timeout:
                break

            try:
                reaction, user = await ctx.bot.wait_for(
                    "reaction_add", timeout=timeout, check=lambda r, u: not bool(u.bot)
                )
            # this seems to raise an odd timeout error, for now just catch-all
            except Exception:
                break

            # check if the reaction should be processed
            if (reaction.message.id != message.id) or (
                restrict and user.id != ctx.author.id
            ):
                # this is checked first so it can pass to the deletion
                pass

            # move forward
            elif str(reaction) == "\u25B6" and index < len(embeds) - 1:
                index += 1
                await message.edit(**get_args(index))

            # move backward
            elif str(reaction) == "\u25C0" and index > 0:
                index -= 1
                await message.edit(**get_args(index))

            # stop pagination
            elif str(reaction) == "\u26D4" and user.id == ctx.author.id:
                break

            # delete embed
            elif str(reaction) == "\U0001F5D1" and user.id == ctx.author.id:
                await message.delete()
                break

            try:
                await reaction.remove(user)
            except Forbidden:
                pass

        try:
            await message.clear_reactions()
        except (Forbidden, NotFound):
            pass

    def task_paginate(self, *args, **kwargs):
        """Creates a pagination task.

        This is useful if you want your command to finish executing when pagination starts.

        parameters:
            ctx (Context): the context object for the message
            *args (...list): the args with which to call the pagination method
            **kwargs (...dict): the keyword args with which to call the pagination method
        """
        self.bot.loop.create_task(self.paginate(*args, **kwargs))
