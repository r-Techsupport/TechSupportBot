import discord

def parse_irc_message(event) -> dict:
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


def parse_ban_message(event) -> dict:
    # Looking for username, hostmask, action, channel, content
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


def format_discord_message(message: discord.Message):
    """This formats the message from discord to prepare for sending to IRC
    Strips new lines and trailing white space

    Args:
        message (discord.Message): The discord message to convert

    Returns:
        str: The formatted message, ready to send to IRC
    """
    IRC_BOLD = ""
    permissions_prefix = get_permissions_prefix_for_discord_user(message.author)
    files = get_file_links(message.attachments)
    message_str = f"{IRC_BOLD}[D]{IRC_BOLD} <{permissions_prefix}"
    message_str += f"{message.author.display_name}> {message.clean_content} {files}"
    message_str = message_str.replace("\n", " ")
    return message_str.strip()

def get_permissions_prefix_for_discord_user(member: discord.Member):
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

def get_file_links(message_attachments: list):
    links = ""
    for attachment in message_attachments:
        links += attachment.url
        links += " "
    return links.strip()