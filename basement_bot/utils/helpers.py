"""Standard helper functions for various use cases.
"""

import os
import re

from discord import Embed


def get_env_value(name, default=None, raise_exception=True):
    """Grabs an env value from the environment and fails if nothing is found.

    Note: this isn't needed for config anymore.

    parameters:
        name (str): the name of the environmental variable
        default (any): the default value to return
        raise_exception (bool): True if an exception should raise on NoneType
    """
    key = os.environ.get(name, default)
    if key is None and raise_exception:
        raise NameError(f"Unable to locate env value: {name}")
    return key


async def tagged_response(ctx, message=None, embed=None):
    """Sends a context response with the original author tagged.

    parameters:
        ctx (Context): the context object
        message (str): the message to send
        embed (discord.Embed): the discord embed object to send
    """
    message = (
        f"{ctx.message.author.mention} {message}"
        if message
        else ctx.message.author.mention
    )
    await ctx.send(message, embed=embed)


async def priv_response(ctx, message=None, embed=None):
    """Sends a context private message to the original author.

    parameters:
        ctx (Context): the context object
        message (str): the message to send
        embed (discord.Embed): the discord embed object to send
    """
    channel = await ctx.message.author.create_dm()
    if message:
        await channel.send(message, embed=embed)
    else:
        await channel.send(embed=embed)


async def emoji_reaction(ctx, emojis):
    """Adds an emoji reaction to the given context message.

    parameters:
        ctx (Context): the context object
        emojis (list, string): the set of (or single) emoji(s) in unicode format
    """
    if not isinstance(emojis, list):
        emojis = [emojis]

    for emoji in emojis:
        await ctx.message.add_reaction(emoji)


async def is_admin(ctx, message_user=True):
    """Context checker for if the author is admin.

    parameters:
        ctx (Context): the context object
        message_user (boolean): True if the user should be notified on failure
    """

    status_ = bool(
        ctx.message.author.id in [int(id) for id in ctx.bot.config.main.admins]
    )

    if not status_:
        if message_user:
            await priv_response(
                ctx, "You must be in the admin list to use this command"
            )
        return False

    return True


def get_guild_from_channel_id(bot, channel_id):
    """Helper for getting the guild associated with a channel.

    parameters:
        bot (BasementBot): the bot object
        channel_id (Union[string, int]): the unique ID of the channel
    """
    for guild in bot.guilds:
        for channel in guild.channels:
            if channel.id == int(channel_id):
                return guild
    return None


def embed_from_kwargs(title=None, description=None, **kwargs):
    """Wrapper for generating an embed from a set of key, values.

    parameters:
        title (str): the title for the embed
        description (str): the description for the embed
        **kwargs (dict): a set of keyword values to be displayed
    """
    embed = Embed(title=title, description=description)
    for key, value in kwargs.items():
        embed.add_field(name=key, value=value, inline=False)
    return embed


def sub_mentions_for_usernames(bot, content):
    """Subs a string of Discord mentions with the corresponding usernames.

    parameters:
        bot (BasementBot): the bot object
        content (str): the content to parse
    """

    def get_nick_from_id_match(match):
        id_ = int(match.group(1))
        user = bot.get_user(id_)
        return f"@{user.name}" if user else "@user"

    return re.sub(r"<@?!?(\d+)>", get_nick_from_id_match, content)


async def delete_message_with_reason(
    ctx, message, reason, private=True, send_original=True
):
    """Deletes a message and provide a reason to the user.

    parameters:
        ctx (Context): the context object for the message
        message (Message): the message object
        reason (str): the reason to provide for deletion
        private (bool): True if the reason should be private messaged
        send_original (bool): True if the user should be provided the original message
    """
    send_func = priv_response if private else tagged_response

    content = message.content
    try:
        await message.delete()
    except Forbidden:
        log.warning(f"Unable to delete message {message.id} due to missing permissions")
        return
    await send_func(ctx, f"Your message was deleted because: `{reason}`")
    if send_original:
        await send_func(ctx, f"Original message: ```{content}```")
