"""Module for static helper code.
"""

import inspect
import json

import discord
import munch


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

        typing_func = getattr(context, "trigger_typing", None)

        if not typing_func:
            await original_callback(*args, **kwargs)
        else:
            try:
                await typing_func()
            except discord.Forbidden:
                pass
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


def get_object_diff(before, after, attrs_to_check):
    """Finds differences in before, after object pairs.

    before (obj): the before object
    after (obj): the after object
    attrs_to_check (list): the attributes to compare
    """
    result = {}

    for attr in attrs_to_check:
        after_value = getattr(after, attr, None)
        if not after_value:
            continue

        before_value = getattr(before, attr, None)
        if not before_value:
            continue

        if before_value != after_value:
            result[attr] = munch.munchify(
                {"before": before_value, "after": after_value}
            )

    return result


def add_diff_fields(embed, diff):
    """Adds fields to an embed based on diff data.

    parameters:
        embed (discord.Embed): the embed object
        diff (dict): the diff data for an object
    """
    for attr, diff_data in diff.items():
        attru = attr.upper()
        if isinstance(diff_data.before, list):
            action = (
                "added" if len(diff_data.before) < len(diff_data.after) else "removed"
            )
            list_diff = set(diff_data.after) ^ set(diff_data.before)

            embed.add_field(
                name=f"{attru} {action}", value=",".join(str(o) for o in list_diff)
            )
            continue

        #Checking if content is a string, and not anything else for guild update.
        if isinstance(diff_data.before, str):
        #expanding the before data to 4096 characters
            embed.add_field(name=f"{attru} (before)", value=diff_data.before[:1024])
            if len(diff_data.before) > 1024:
                embed.add_field(name=f"{attru} (before continue)",value=diff_data.before[1025:2048])
            if len(diff_data.before) > 2048 and len(diff_data.after) <= 2800:
                embed.add_field(name=f"{attru} (before continue)",value=diff_data.before[2049:3072])
            if len(diff_data.before) > 3072 and len(diff_data.after) <= 1800:
                embed.add_field(name=f"{attru} (before continue)",value=diff_data.before[3073:4096])

            #expanding the after data to 4096 characters
            embed.add_field(name=f"{attru} (after)", value=diff_data.after[:1024])
            if len(diff_data.after) > 1024:
                embed.add_field(name=f"{attru} (after continue)", value=diff_data.after[1025:2048])
            if len(diff_data.after) > 2048:
                embed.add_field(name=f"{attru} (after continue)", value=diff_data.after[2049:3072])
            if len(diff_data.after) > 3072:
                embed.add_field(name=f"{attru} (after continue)", value=diff_data.after[3073:4096])
        else:
            embed.add_field(name=f"{attru} (before)", value=diff_data.before or None)
            embed.add_field(name=f"{attru} (after)", value=diff_data.after or None)
    return embed
