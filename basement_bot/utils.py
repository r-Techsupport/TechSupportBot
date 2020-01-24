"""Module for helper functions.
"""

import os


def get_env_value(name, raise_exception=True):
    """Grabs an env value from the environment and fails if nothing is found.

    parameters:
        name (str): the name of the environmental variable
        raise_exception (bool): True if an exception should be raised
    """

    key = os.environ.get(name, None)
    if not key:
        if raise_exception:
            raise NameError(f"Unable to locate env value: {name}")
    return key


async def tagged_response(ctx, message):
    """Sends a context response with the original author tagged.

    parameters:
        ctx (ctx): the context object
        message (str): the message to send
    """

    await ctx.send(f"{ctx.message.author.mention} {message}")
