"""
This is a collection of functions designed to be used by many extensions
This replaces duplicate or similar code across many extensions
"""

import discord


def generate_basic_embed(
    title: str, description: str, color: discord.Color, url: str = None
) -> discord.Embed:
    """Generates a basic embed

    Args:
        title (str): The title to be assigned to the embed
        description (str): The description to be assigned to the embed
        color (discord.Color): The color to be assigned to the embed
        url (str, optional): A URL for a thumbnail picture. Defaults to None.

    Returns:
        discord.Embed: The formatted embed, styled with the 4 above options
    """
    embed = discord.Embed()
    embed.title = title
    embed.description = description
    embed.color = color
    if url:
        embed.set_thumbnail(url=url)
    return embed


async def search_channel_for_message(
    channel: discord.TextChannel,
    prefix: str = None,
    member_to_match: discord.Member = None,
    content_to_match: str = None,
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
            and (content_to_match is None or content_to_match in message.content)
            and (prefix is None or not message.content.startswith(prefix))
            and (allow_bot is True or not message.author.bot)
        ):
            return message
    return None