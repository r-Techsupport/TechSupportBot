"""Standard helper functions for various use cases.
"""

import os


def get_env_value(name, default=None, raise_exception=True):
    """Grabs an env value from the environment and fails if nothing is found.

    parameters:
        name (str): the name of the environmental variable
        default (any): the default value to return
        raise_exception (bool): True if an exception should raise on NoneType
    """
    key = os.environ.get(name, default)
    if key is None and raise_exception:
        raise NameError(f"Unable to locate env value: {name}")
    return key


async def tagged_response(ctx, message):
    """Sends a context response with the original author tagged.

    parameters:
        ctx (Context): the context object
        message (str): the message to send
    """
    await ctx.send(f"{ctx.message.author.mention} {message}")


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


async def priv_response(ctx, message):
    """Sends a context private message to the original author.

    parameters:
        ctx (Context): the context object
        message (str): the message to send
    """
    channel = await ctx.message.author.create_dm()
    await channel.send(message)


async def is_admin(ctx):
    """Context checker for if the author is admin.

    parameters:
        ctx (Context): the context object
    """
    admins = get_env_value("ADMINS", raise_exception=False)
    admins = admins.replace(" ", "").split(",") if admins else []

    status_ = bool(ctx.message.author.id in [int(id) for id in admins])

    if not status_:
        await priv_response(ctx, "You must be in the admin list to use this command")
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
