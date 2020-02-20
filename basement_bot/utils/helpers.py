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
    admins = admins.replace(" ", "").split(",")
    status_ = bool(ctx.message.author.id in [int(id) for id in admins])

    if not status_:
        await priv_response(ctx, "You must be in the admin list to use this command")
        return False

    return True
