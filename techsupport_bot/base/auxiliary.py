"""
This is a collection of functions designed to be used by many extensions
This replaces duplicate or similar code across many extensions
"""

import inspect
import json
from functools import wraps
from typing import Any

import discord
import munch


def generate_basic_embed(
    title: str,
    description: str | None = None,
    color: discord.Color | None = None,
    url: str = "",
    all_inline: bool = False,
    **fields: Any,
) -> discord.Embed:
    """Generates an embed with the given properties and populated with the given
    fields.

    Args:
        title (str): The title to be assigned to the embed
        description (str): The description to be assigned to the embed
        color (discord.Color): The color to be assigned to the embed
        url (str, optional): A URL for a thumbnail picture. Defaults to "".
        all_inline (bool): True if all fields should be added with inline=True
        fields (dict): A dictionary containing the title and content of embed fields

    Returns:
        discord.Embed: The formatted embed, styled with the 4 above options
    """
    embed = discord.Embed()
    embed.title = title
    embed.description = description
    embed.color = color
    if url != "":
        embed.set_thumbnail(url=url)
    for key, value in fields.items():
        embed.add_field(name=key, value=value, inline=all_inline)
    return embed


async def search_channel_for_message(
    channel: discord.abc.Messageable,
    prefix: str = "",
    member_to_match: discord.Member = None,
    content_to_match: str = "",
    allow_bot: bool = True,
) -> discord.Message:
    """Searches the last 50 messages in a channel based on given conditions

    Args:
        channel (discord.TextChannel): The channel to search in. This is required
        prefix (str, optional): A prefix you want to exclude from the search. Defaults to None.
        member_to_match (discord.Member, optional): The member that the
            message found must be from. Defaults to None.
        content_to_match (str, optional): The content the message must contain. Defaults to None.
        allow_bot (bool, optional): If you want to allow messages to
            be authored by a bot. Defaults to True

    Returns:
        discord.Message: The message object that meets the given critera.
            If none could be found, None is returned
    """

    SEARCH_LIMIT = 50

    async for message in channel.history(limit=SEARCH_LIMIT):
        if (
            (member_to_match is None or message.author == member_to_match)
            and (content_to_match == "" or content_to_match in message.content)
            and (prefix == "" or not message.content.startswith(prefix))
            and (allow_bot is True or not message.author.bot)
        ):
            return message
    return None


async def add_list_of_reactions(message: discord.Message, reactions: list) -> None:
    """A very simple method to add reactions to a message
    This only exists to be a single function to change in the event of an API update

    Args:
        message (discord.Message): The message to add reations to
        reactions (list): A list of all unicode emojis to add
    """
    for emoji in reactions:
        await message.add_reaction(emoji)


def construct_mention_string(targets: list[discord.User]) -> str:
    """Builds a string of mentions from a list of users.

    parameters:
        targets ([]discord.User): the list of users to mention
    """
    constructed = set()

    # construct mention string
    user_mentions = ""
    for index, target in enumerate(targets):
        mid = getattr(target, "id", 0)
        if mid in constructed:
            continue

        mention = getattr(target, "mention", None)
        if not mention:
            continue

        constructed.add(mid)

        spacer = " " if (index != len(targets) - 1) else ""
        user_mentions += mention + spacer

    if user_mentions.endswith(" "):
        user_mentions = user_mentions[:-1]

    if len(user_mentions) == 0:
        return None

    return user_mentions


def prepare_deny_embed(message: str) -> discord.Embed:
    """Prepares a formatted deny embed
    This just calls generate_basic_embed with a pre-loaded set of args

    Args:
        message (str): The reason for deny

    Returns:
        discord.Embed: The formatted embed
    """
    return generate_basic_embed(
        title="😕 👎",
        description=message,
        color=discord.Color.red(),
    )


async def send_deny_embed(
    message: str, channel: discord.abc.Messageable, author: discord.Member | None = None
) -> discord.Message:
    """Sends a formatted deny embed to the given channel

    Args:
        message (str): The reason for deny
        channel (discord.abc.Messageable): The channel to send the deny embed to
        author (discord.Member, optional): The author of the message.
            If this is provided, the author will be mentioned

    Returns:
        discord.Message: The message object sent
    """
    embed = prepare_deny_embed(message)
    message = await channel.send(
        content=construct_mention_string([author]), embed=embed
    )
    return message


def prepare_confirm_embed(message: str) -> discord.Embed:
    """Prepares a formatted confirm embed
    This just calls generate_basic_embed with a pre-loaded set of args

    Args:
        message (str): The reason for confirm

    Returns:
        discord.Embed: The formatted embed
    """
    return generate_basic_embed(
        title="😄 👍",
        description=message,
        color=discord.Color.green(),
    )


async def send_confirm_embed(
    message: str, channel: discord.abc.Messageable, author: discord.Member | None = None
) -> discord.Message:
    """Sends a formatted deny embed to the given channel

    Args:
        message (str): The reason for confirm
        channel (discord.abc.Messageable): The channel to send the confirm embed to
        author (discord.Member, optional): The author of the message.
            If this is provided, the author will be mentioned

    Returns:
        discord.Message: The message object sent
    """
    embed = prepare_confirm_embed(message)
    message = await channel.send(
        content=construct_mention_string([author]), embed=embed
    )
    return message


async def get_json_from_attachments(
    message: discord.Message, as_string: bool = False, allow_failure: bool = False
) -> munch.Munch | str | None:
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


def config_schema_matches(input_config: dict, current_config: dict) -> list[str] | None:
    """Performs a schema check on an input guild config.

    parameters:
        input_config (dict): the config to be added
        current_config (dict): the current config
    """
    if (
        any(key not in current_config for key in input_config.keys())
        or len(current_config) != len(input_config) + 1
    ):
        added_keys = []
        removed_keys = []

        for key in input_config.keys():
            if key not in current_config and key != "_id":
                added_keys.append(key)

        for key in current_config.keys():
            if key not in input_config and key != "_id":
                removed_keys.append(key)

        result = []
        for key in added_keys:
            result.append("added: " + key)

        for key in removed_keys:
            result.append("removed: " + key)

        return result

    return None


def with_typing(command: discord.ext.commands.Command) -> discord.ext.commands.Command:
    """Decorator for commands to utilize "async with" ctx.typing()

    This will show the bot as typing... until the command completes

    parameters:
        command (discord.ext.commands.Command): the command object to modify
    """
    original_callback = command.callback

    @wraps(original_callback)
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
                await original_callback(*args, **kwargs)

    # this has to be done so invoke will see the original signature
    typing_wrapper.__name__ = command.name

    # calls the internal setter
    command.callback = typing_wrapper
    command.callback.__module__ = original_callback.__module__

    return command


def preserialize_object(obj: object) -> dict:
    """Provides sane object -> dict transformation for most objects.

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


def get_object_diff(
    before: object, after: object, attrs_to_check: list
) -> munch.Munch | dict:
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


def add_diff_fields(embed: discord.Embed, diff: dict) -> discord.Embed:
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
            list_diff = set(repr(diff_data.after)) ^ set(repr(diff_data.before))

            embed.add_field(
                name=f"{attru} {action}", value=",".join(str(o) for o in list_diff)
            )
            continue

        # Checking if content is a string, and not anything else for guild update.
        if isinstance(diff_data.before, str):
            # expanding the before data to 4096 characters
            embed.add_field(name=f"{attru} (before)", value=diff_data.before[:1024])
            if len(diff_data.before) > 1024:
                embed.add_field(
                    name=f"{attru} (before continue)", value=diff_data.before[1025:2048]
                )
            if len(diff_data.before) > 2048 and len(diff_data.after) <= 2800:
                embed.add_field(
                    name=f"{attru} (before continue)", value=diff_data.before[2049:3072]
                )
            if len(diff_data.before) > 3072 and len(diff_data.after) <= 1800:
                embed.add_field(
                    name=f"{attru} (before continue)", value=diff_data.before[3073:4096]
                )

            # expanding the after data to 4096 characters
            embed.add_field(name=f"{attru} (after)", value=diff_data.after[:1024])
            if len(diff_data.after) > 1024:
                embed.add_field(
                    name=f"{attru} (after continue)", value=diff_data.after[1025:2048]
                )
            if len(diff_data.after) > 2048:
                embed.add_field(
                    name=f"{attru} (after continue)", value=diff_data.after[2049:3072]
                )
            if len(diff_data.after) > 3072:
                embed.add_field(
                    name=f"{attru} (after continue)", value=diff_data.after[3073:4096]
                )
        else:
            embed.add_field(name=f"{attru} (before)", value=diff_data.before or None)
            embed.add_field(name=f"{attru} (after)", value=diff_data.after or None)
    return embed
