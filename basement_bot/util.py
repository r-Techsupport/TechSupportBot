"""Module for static helper code.
"""

import inspect
import json

import discord
import embeds
import munch


async def send_with_mention(ctx, content=None, targets=None, **kwargs):
    """Sends a context response with the original author tagged.

    parameters:
        ctx (discord.ext.Context): the context object
        content (str): the message to send
        targets ([discord.Member]): the Discord users to tag (defaults to context)
    """
    if targets is None:
        targets = [ctx.message.author]

    user_mentions = ""
    for index, target in enumerate(targets):
        mention = getattr(target, "mention", None)
        if not mention:
            continue
        spacer = " " if (index != len(targets) - 1) else ""
        user_mentions += mention + spacer

    content = f"{user_mentions} {content}" if content else user_mentions
    message = await ctx.send(content=content, **kwargs)
    return message


async def send_confirm_embed(ctx, message, target=None):
    """Sends a confirmation embed.

    parameters:
        message (str): the base confirmation message
        target (discord.Member): the Discord user to tag (defaults to context)
    """
    embed = embeds.ConfirmEmbed(message=message)
    message = await send_with_mention(ctx, embed=embed, targets=[target])
    return message


async def send_deny_embed(ctx, message, target=None):
    """Sends a deny embed.

    parameters:
        message (str): the base deny message
        target (discord.Member): the Discord user to tag (defaults to context)
    """
    embed = embeds.DenyEmbed(message=message)
    message = await send_with_mention(ctx, embed=embed, targets=[target])
    return message


async def get_json_from_attachments(message, as_string=False, allow_failure=False):
    """Returns concatted JSON from a message's attachments.

    parameters:
        ctx (discord.ext.Context): the context object for the message
        message (Message): the message object
        as_string (bool): True if the serialized JSON should be returned
        allow_failure (bool): True if an exception should be ignored when parsing attachments
    """
    if not message.attachments:
        return None

    attachment_jsons = []
    for attachment in message.attachments:
        try:
            json_bytes = await attachment.read()
            attachment_jsons.append(json.loads(json_bytes.decode("UTF-8")))
        except Exception as exception:
            if allow_failure:
                continue
            raise exception

    if len(attachment_jsons) == 1:
        attachment_jsons = attachment_jsons[0]

    return (
        json.dumps(attachment_jsons) if as_string else munch.munchify(attachment_jsons)
    )


def generate_embed_from_kwargs(
    title=None,
    description=None,
    all_inline=False,
    cls=None,
    **kwargs,
):
    """Wrapper for generating an embed from a set of key, values.

    parameters:
        title (str): the title for the embed
        description (str): the description for the embed
        all_inline (bool): True if all fields should be added with inline=True
        cls (discord.Embed): the embed class to use
        kwargs (dict): a set of keyword values to be displayed
    """
    if not cls:
        cls = discord.Embed

    embed = cls(title=title, description=description)
    for key, value in kwargs.items():
        embed.add_field(name=key, value=value, inline=all_inline)
    return embed


def ipc_response(code=200, error=None, payload=None):
    """Makes a response object for an IPC client.

    parameters:
        code (int): the HTTP-like status code
        error (str): the response error message
        payload (dict): the optional data payload
    """
    return {"code": code, "error": error, "payload": payload}


def config_schema_matches(input_config, current_config):
    """Performs a schema check on an input guild config.

    parameters:
        input_config (dict): the config to be added
        current_config (dict): the current config
    """
    if (
        any(key not in current_config for key in input_config.keys())
        or len(current_config) != len(input_config) + 1
    ):
        return False

    return True


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
    command.callback.__module__ = original_callback.__module__

    return command


def preserialize_object(obj):
    """Provides sane object -> dict transformation for most objects.

    This is primarily used to send Discord.py object data via the IPC server.

    parameters;
        obj (object): the object to serialize
    """
    attributes = inspect.getmembers(obj, lambda a: not inspect.isroutine(a))
    filtered_attributes = filter(
        lambda e: not (e[0].startswith("__") and e[0].endswith("__")), attributes
    )

    data = {}
    for name, attr in filtered_attributes:
        # remove single underscores
        if name.startswith("_"):
            name = name[1:]

        # if it's not a basic type, stringify it
        # only catch: nested data is not readily JSON
        if isinstance(attr, list):
            attr = [str(element) for element in attr]
        elif isinstance(attr, dict):
            attr = {str(key): str(value) for key, value in attr.items()}
        elif isinstance(attr, int):
            attr = str(attr)
        elif isinstance(attr, float):
            pass
        else:
            attr = str(attr)

        data[str(name)] = attr

    return data
