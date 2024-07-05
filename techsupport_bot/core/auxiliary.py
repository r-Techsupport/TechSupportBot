"""
This is a collection of functions designed to be used by many extensions
This replaces duplicate or similar code across many extensions
"""

from __future__ import annotations

import json
from functools import wraps
from typing import TYPE_CHECKING, Any

import discord
import munch
import ui
from discord.ext import commands

if TYPE_CHECKING:
    import cogs

default_color = discord.Color.blurple()


def generate_basic_embed(
    title: str = "",
    description: str = "",
    color: discord.Color = default_color,
    url: str = "",
) -> discord.Embed:
    """Generates a basic embed

    Args:
        title (str, optional): The title to be assigned to the embed. Defaults to "".
        description (str, optional): The description to be assigned to the embed. Defaults to "".
        color (discord.Color, optional): The color to be assigned to the embed.
            Defaults to blurple.
        url (str, optional): A URL for a thumbnail picture. Defaults to "".

    Returns:
        discord.Embed: The formatted embed, styled with the 4 above options
    """
    embed = discord.Embed()
    embed.title = title
    embed.description = description
    embed.color = color
    if url != "":
        embed.set_thumbnail(url=url)
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
        channel (discord.abc.Messageable): The channel to search in. This is required
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

    Args:
        targets (list[discord.User]): the list of users to mention

    Returns:
        str: A string containing space separated user mention code
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
        author (discord.Member | None, optional): The author of the message.
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
        author (discord.Member | None, optional): The author of the message.
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

    Args:
        message (discord.Message): the message object
        as_string (bool, optional): True if the serialized JSON should be returned.
            Defaults to False.
        allow_failure (bool, optional): True if an exception should be ignored when
            parsing attachments. Defaults to False.

    Raises:
        exception: If allow_failure is False, this raises ANY exception caught while parsing

    Returns:
        munch.Munch | str | None: The json formatted as requested by as_string and allow_failure
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

    Args:
        input_config (dict): the config to be added
        current_config (dict): the current config

    Returns:
        list[str] | None: Returns a list of changes to the config, if it was changed.
            Otherwise returns nothing, signifying no changes
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


def with_typing(command: commands.Command) -> commands.Command:
    """Decorator for commands to utilize "async with" ctx.typing()

    This will show the bot as typing... until the command completes

    Args:
        command (commands.Command): the command object to modify

    Returns:
        commands.Command: The modified command wrapped with the typing call
    """
    original_callback = command.callback

    @wraps(original_callback)
    async def typing_wrapper(*args: tuple, **kwargs: dict[str, Any]) -> None:
        """The wrapper to add typing to any given function and call the original function

        Args:
            *args (tuple): Used to preserve any and all original arguments to the original command
            **kwargs (dict[str, Any]): Used to preserve any and all original arguments
                to the original command
        """
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


def get_object_diff(before: object, after: object, attrs_to_check: list) -> munch.Munch:
    """Finds differences in before, after object pairs.

    Args:
        before (object): the before object
        after (object): the after object
        attrs_to_check (list): the attributes to compare

    Returns:
        munch.Munch: The set of differences, will contain a .before
            and a .after index, with everything changed
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

    Args:
        embed (discord.Embed): the embed object
        diff (dict): the diff data for an object

    Returns:
        discord.Embed: Shows the difference between two objects in an embed
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


def get_help_embed_for_extension(
    cog: cogs.BaseCog, extension_name: str, command_prefix: str
) -> discord.Embed:
    """Gets the help embed for an extension.

    Defined so it doesn't have to be written out twice

    Args:
        cog (cogs.BaseCog): The cog that needs the commands put into a help menu
        extension_name (str): the name of the extension to show the help for
        command_prefix (str): passed to the func as it has to be awaited

    Returns:
        discord.Embed: Embed containing all commands with their description
    """
    embed = discord.Embed()
    embed.title = f"Extension Commands: `{extension_name}`"

    # Sorts commands alphabetically
    command_list = list(cog.bot.walk_commands())
    command_list.sort(key=lambda command: command.name)

    # Loops through every command in the bots library
    for command in command_list:
        # Gets the command name
        command_extension_name = cog.bot.get_command_extension_name(command)

        # Continues the loop if the command isn't a part of the target extension
        if extension_name != command_extension_name or issubclass(
            command.__class__, commands.Group
        ):
            continue

        if command.full_parent_name == "":
            syntax = f"{command_prefix}{command.name}"

        else:
            syntax = f"{command_prefix}{command.full_parent_name} {command.name}"

        usage = command.usage or ""

        embed.add_field(
            name=f"`{syntax} {usage}`",
            value=command.description or "No description available",
            inline=False,
        )

    # Default for when no matching commands were found
    if len(embed.fields) == 0:
        embed.description = "There are no commands for this extension"

    return embed


async def extension_help(
    cog: cogs.BaseCog, ctx: commands.Context, extension_name: str
) -> None:
    """Automatically prompts for help if improper syntax for an extension is called.

    The format for extension_name that's used is `self.__module__[11:]`, because
    all extensions have the value set to extension.<name>, it's the most reliable
    way to get the extension name regardless of aliases

    Args:
        cog (cogs.BaseCog): The cog that needs the commands put into a help menu
        ctx (commands.Context): context of the message
        extension_name (str): the name of the extension to show the help for
    """

    # Checks whether the first given argument is valid if an argument is supplied
    if len(ctx.message.content.split()) > 1:
        arg = ctx.message.content.split().pop(1)
        valid_commands = []
        valid_args = []
        # Loops through each command for said extension
        for command in cog.bot.get_cog(cog.qualified_name).walk_commands():
            valid_commands.append(command.name)
            valid_args.append(command.aliases)

        # Flatmaps nested lists, because aliases are returned as lists.
        valid_args = [item for sublist in valid_args for item in sublist]

        # If argument isn't a valid command or alias, wait for confirmation to show help page
        if arg not in valid_args and arg not in valid_commands:
            view = ui.Confirm()
            await view.send(
                message="Invalid argument! Show help command?",
                channel=ctx.channel,
                author=ctx.author,
                timeout=10,
            )
            await view.wait()
            if view.value != ui.ConfirmResponse.CONFIRMED:
                return

            await ctx.send(
                embed=get_help_embed_for_extension(
                    cog, extension_name, await cog.bot.get_prefix(ctx.message)
                )
            )

    # Executed if no arguments were supplied
    elif len(ctx.message.content.split()) == 1:
        await ctx.send(
            embed=get_help_embed_for_extension(
                cog, extension_name, await cog.bot.get_prefix(ctx.message)
            )
        )


async def bot_admin_check_context(ctx: commands.Context) -> bool:
    """A simple check to put on a prefix command function to ensure that the caller is an admin

    Args:
        ctx (commands.Context): The context that the command was called in

    Raises:
        MissingPermissions: If the user is not a bot admin

    Returns:
        bool: True if can run
    """
    is_admin = await ctx.bot.is_bot_admin(ctx.author)
    if not is_admin:
        raise commands.MissingPermissions(["bot_admin"])
    return True
