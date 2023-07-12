"""
This is a collection of functions designed to be used by many extensions
This replaces duplicate or similar code across many extensions
"""

import discord


def generate_basic_embed(
    title: str, description: str, color: discord.Color, url: str = ""
) -> discord.Embed:
    """Generates a basic embed

    Args:
        title (str): The title to be assigned to the embed
        description (str): The description to be assigned to the embed
        color (discord.Color): The color to be assigned to the embed
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


def construct_mention_string(targets: list) -> str:
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
    message: str, channel: discord.abc.Messageable, author: discord.Member = None
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
    message: str, channel: discord.abc.Messageable, author: discord.Member = None
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
