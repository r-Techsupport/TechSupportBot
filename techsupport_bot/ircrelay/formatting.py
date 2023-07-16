"""A bunch of functions to format messages going to and from IRC"""
from typing import Dict, List

import discord
import irc.client


def parse_irc_message(event: irc.client.Event) -> Dict[str, str]:
    """This turns the irc.client.Event object into a dictionary
    This dictionary contains more direct access to import information
    This gets username, hostmask, channel, and raw content

    Args:
        event (irc.client.Event): The event object that triggered this function

    Returns:
        Dict[str, str]: The formatted message
    """
    # Looking for username, hostmask, action, channel, content
    username = event.source.split("!")[0]
    hostmask = event.source.split("!")[1]
    channel = event.target
    content = event.arguments[0]

    return {
        "username": username,
        "hostmask": hostmask,
        "channel": channel,
        "content": content,
    }


def parse_ban_message(event: irc.client.Event) -> Dict[str, str]:
    """This turns the irc.client.Event object into a dictionary
    This dictionary contains more direct access to import information
    This gets username, hostmask, channel
    Content in this case is a special readable user was banned/unbanned

    Args:
        event (irc.client.Event): The event object that triggered this function

    Returns:
        Dict[str, str]: The formatted message
    """
    username = event.source.split("!")[0]
    hostmask = event.source.split("!")[1]
    channel = event.target

    if "+b" in event.arguments[0]:
        action = "banned"
    elif "+b" in event.arguments[0]:
        action = "unbanned"
    content = f"{event.arguments[1]} was {action} from {channel}"

    return {
        "username": username,
        "hostmask": hostmask,
        "channel": channel,
        "content": content,
    }


def format_discord_message(
    message: discord.Message, content_override: str = None
) -> str:
    """This formats the message from discord to prepare for sending to IRC
    Strips new lines and trailing white space

    Args:
        message (discord.Message): The discord message to convert
        content_override (str): If passed, this will changed the content of the message

    Returns:
        str: The formatted message, ready to send to IRC
    """
    message_str = core_sent_message_format(
        message=message, content_override=content_override
    )
    return message_str


def core_sent_message_format(
    message: discord.Message, content_override: str = None
) -> str:
    """This formats a message, adds a permissions prefix, user prefix, and fixes new lines and
    file attachements

    Args:
        message (discord.Message): The discord message object to format
        content_override (str): If passed, this will changed the content of the message

    Returns:
        str: The string, with unlimited length, that is ready to be sent to IRC
    """
    use_content = content_override if content_override else message.clean_content
    IRC_BOLD = ""
    permissions_prefix = get_permissions_prefix_for_discord_user(member=message.author)
    files = get_file_links(message_attachments=message.attachments)
    message_content = f"{use_content} {files}"
    if len(message_content.strip()) == 0:
        return ""
    message_str = f"{IRC_BOLD}[D]{IRC_BOLD} <{permissions_prefix}"
    message_str += f"{message.author.display_name}> {message_content}"
    message_str = message_str.replace("\n", " ")
    message_str = message_str.strip()
    return message_str


def format_discord_edit_message(message: discord.Message) -> str:
    """This modifies a formatted message to add a message edited flag

    Args:
        message (discord.Message): The discord message object to format

    Returns:
        str: The string that is ready to be sent to IRC. Complete with message edited flag
    """
    message_str = core_sent_message_format(message=message)
    message_str = f"{message_str} ** (message edited)"
    return message_str


def format_discord_reaction_message(
    message: discord.Message, user: discord.User, reaction: discord.Reaction
) -> str:
    """This modifies a formatted message to add a prefix stating a reaction was added

    Args:
        message (discord.Message): _description_
        user (discord.User): The user who added the reaction
        reaction (discord.Reaction): The reaction that was added to the message

    Returns:
        str: The string that is ready to be sent to IRC, with a prefix showing the reaction
    """
    # Deal with custom vs global emoji
    if hasattr(reaction.emoji, "name"):
        emoji = reaction.emoji.name
    else:
        emoji = f":{reaction.emoji}:"

    message_str = core_sent_message_format(message=message)
    message_str = f"{user.display_name}  reacted with {emoji} to {message_str}"
    return message_str


def get_permissions_prefix_for_discord_user(member: discord.Member) -> str:
    """Gets the correct prefix based on permissions to prefix in IRC

    Args:
        member (discord.Member): The member object who sent the message in discord

    Returns:
        str: The string containing the prefix. Could be empty
    """
    prefix_str = ""
    if member.guild_permissions.administrator:
        prefix_str += "*"
    if member.guild_permissions.ban_members:
        prefix_str += "*"
    return prefix_str


def get_file_links(message_attachments: List[discord.Attachment]) -> str:
    """Turns a list of attachments into a string containing links to them

    Args:
        message_attachments (List[discord.Attachment]): The list of attachments from a
        discord.Message object

    Returns:
        str: The str containing space a seperated list of urls
    """
    links = ""
    for attachment in message_attachments:
        links += attachment.url
        links += " "
    return links.strip()
