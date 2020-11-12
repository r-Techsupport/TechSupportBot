"""Standard helper functions for various use cases.
"""

import ast
import datetime
import os
import re

from discord import Embed, Forbidden, NotFound


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

    id_is_admin = bool(
        ctx.message.author.id in [int(id) for id in ctx.bot.config.main.admins.ids]
    )
    role_is_admin = False
    for role in getattr(ctx.message.author, "roles", []):
        if role.name in ctx.bot.config.main.admins.roles:
            role_is_admin = True
            break

    if any([id_is_admin, role_is_admin]):
        return True

    if message_user:
        await priv_response(ctx, "You must be an admin to use this command")
    return False


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


async def delete_message_with_reason(ctx, message, reason, private=True, original=True):
    """Deletes a message and provide a reason to the user.

    parameters:
        ctx (Context): the context object for the message
        message (Message): the message object
        reason (str): the reason to provide for deletion
        private (bool): True if the reason should be private messaged
        original (bool): True if the user should be provided the original message
    """
    send_func = priv_response if private else tagged_response

    content = message.content
    try:
        await message.delete()
    except (Forbidden, NotFound):
        return

    await send_func(ctx, f"Your message was deleted because: `{reason}`")
    if original:
        await send_func(ctx, f"Original message: ```{content}```")


async def get_json_from_attachment(message):
    """Returns a JSON object parsed from a message's attachment.

    parameters:
        message (Message): the message object
    """
    try:
        json_bytes = await message.attachments[0].read()
        json_str = json_bytes.decode("UTF-8")
        return ast.literal_eval(json_str)
    except Exception:
        return None


async def paginate(ctx, embeds, timeout=300, tag_user=False):
    """Paginates a set of embed objects for users to sort through

    parameters:
        ctx (Context): the context object for the message
        embeds (discord.Embed[]): the embeds to paginate (one embed per page)
        timeout (int) (seconds): the time to wait before exiting the reaction listener
        tag_user (bool): True if the context user should be mentioned in the response
    """
    for index, embed in enumerate(embeds):
        embed.set_footer(text=f"Page {index+1}")

    start_time = datetime.datetime.now()
    index = 0

    if tag_user:
        message = await tagged_response(ctx, embed=embeds[index])
    else:
        message = await ctx.send(embed=embeds[index])

    await message.add_reaction("\u25C0")
    await message.add_reaction("\u25B6")

    while True:

        check = lambda r, u: r.message.id == message.id

        try:
            reaction, user = await ctx.bot.wait_for(
                "reaction_add", timeout=timeout, check=check
            )
        except Exception:
            break

        if user.bot:
            continue

        if (datetime.datetime.now() - start_time).seconds > timeout:
            break

        if str(reaction) == "\u25B6" and index < len(embeds) - 1:
            # move forward
            index += 1
            await message.edit(embed=embeds[index])

        elif str(reaction) == "\u25C0" and index > 0:
            # move backward
            index -= 1
            await message.edit(embed=embeds[index])

        try:
            await reaction.remove(user)
        except Forbidden:
            pass

    try:
        await message.delete()
    except Forbidden:
        pass
