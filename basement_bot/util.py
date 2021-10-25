"""Module for static helper code.
"""

import json

import aiohttp
import discord
import munch


async def send_with_mention(ctx, content=None, target=None, **kwargs):
    """Sends a context response with the original author tagged.

    parameters:
        ctx (discord.ext.Context): the context object
        content (str): the message to send
        target (discord.Member): the Discord user to tag
    """
    user_mention = target.mention if target else ctx.message.author.mention
    content = f"{user_mention} {content}" if content else user_mention
    message = await ctx.send(content=content, **kwargs)
    return message


async def get_json_from_attachments(message, as_string=False, allow_failure=False):
    """Returns concatted JSON from a message's attachments.

    parameters:
        ctx (discord.ext.Context): the context object for the message
        message (Message): the message object
        as_string (bool): True if the serialized JSON should be returned
        allow_failure (bool): True if an exception should be ignored when parsing attachments
    """
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
    elif len(attachment_jsons) == 0:
        attachment_jsons = {}

    return (
        json.dumps(attachment_jsons) if as_string else munch.munchify(attachment_jsons)
    )


def generate_embed_from_kwargs(
    title=None, description=None, all_inline=False, **kwargs
):
    """Wrapper for generating an embed from a set of key, values.

    parameters:
        title (str): the title for the embed
        description (str): the description for the embed
        all_inline (bool): True if all fields should be added with inline=True
        kwargs (dict): a set of keyword values to be displayed
    """
    embed = discord.Embed(title=title, description=description)
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


async def http_call(method, url, *args, **kwargs):
    """Makes an HTTP request.

    By default this returns JSON/dict with the status code injected.

    parameters:
        method (str): the HTTP method to use
        url (str): the URL to call
        get_raw_response (bool): True if the actual response object should be returned
    """
    client = aiohttp.ClientSession()

    method_fn = getattr(client, method.lower())

    get_raw_response = kwargs.pop("get_raw_response", False)
    response_object = await method_fn(url, *args, **kwargs)

    if get_raw_response:
        response = response_object
    else:
        response_json = await response_object.json()
        response = munch.munchify(response_json) if response_object else munch.Munch()
        response["status_code"] = getattr(response_object, "status", None)

    await client.close()

    return response


def config_schema_matches(input_config, current_config):
    """Performs a schema check on an input config.

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
