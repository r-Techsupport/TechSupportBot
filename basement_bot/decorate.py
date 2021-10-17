"""Misc decorators (not attached to the bot object)
"""

import inspect

import discord


def with_typing(command):
    """Decorator for commands to utilize "async with" ctx.typing()

    This will show the bot as typing... until the command completes

    parameters:
        command (discord.ext.commands.Command): the command object to modify
    """
    original_callback = command.callback
    original_signature = inspect.signature(original_callback)

    async def typing_wrapper(*args, **kwargs):
        context = args[1]

        typing_func = getattr(context, "typing", None)

        if not typing_func:
            await original_callback(*args, **kwargs)
        else:
            try:
                async with typing_func():
                    await original_callback(*args, **kwargs)
            except discord.Forbidden:
                # sometimes the discord API doesn't like this
                # proceed without typing
                await original_callback(*args, **kwargs)

    # this has to be done so invoke will see the original signature
    typing_wrapper.__signature__ = original_signature
    typing_wrapper.__name__ = command.name

    # calls the internal setter
    command.callback = typing_wrapper

    return command
