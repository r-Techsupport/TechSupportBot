from discord.ext import commands
from emoji import EMOJI_UNICODE

from utils.helpers import (emoji_reaction, get_env_value, priv_response,
                           tagged_response)

SEARCH_LIMIT = 20

COMMAND_PREFIX = get_env_value("COMMAND_PREFIX")


def setup(bot):
    bot.add_command(emsg)
    bot.add_command(ermsg)


def emoji_from_char(char):
    return EMOJI_UNICODE.get(f":regional_indicator_symbol_letter_{char.lower()}:")


def emoji_message_from_string(string):
    emoji_message = ""
    registered = False
    for char in string:
        emoji_ = emoji_from_char(char)
        if emoji_:
            emoji_message += emoji_ + " "
            registered = True
        else:
            emoji_message += char + " "
    if not emoji_message or not registered:
        return None
    return emoji_message


def emoji_reaction_from_string(string):
    found = {}
    emoji_list = []
    for char in string:
        if char == " ":
            continue
        if found.get(char):
            return None
        emoji_ = emoji_from_char(char)
        if emoji_:
            emoji_list.append(emoji_)
            found[char] = True
        else:
            return None
    if not emoji_list:
        return None
    return emoji_list


@commands.command(
    name="emsg",
    brief=emoji_message_from_string("Emoji message!"),
    description="Creates a regional_indiciator_X emoji message.",
    usage="[message]",
)
async def emsg(ctx, *args):
    message = " ".join(args[:-1]) if args else None
    if not message:
        await priv_response(ctx, "You must specify a message!")
        return

    emoji_message = emoji_message_from_string(message)
    if emoji_message:
        await tagged_response(ctx, emoji_message)
    else:
        await priv_response(ctx, "I can't get any emoji letters from your message!")


@commands.command(
    name="ermsg",
    brief=emoji_message_from_string("Same thing but in a reaction"),
    description="Creates a regional_indiciator_X emoji reaction for a user's most recent message.",
    usage="[message] @user",
)
async def ermsg(ctx, *args):
    message = " ".join(args[:-1]) if args else None
    if not message:
        await priv_response(ctx, "You must specify a message!")
        return

    if not len(ctx.message.mentions) == 1:
        await priv_response(ctx, "You must mention a specific user to react to!")
        return
    react_user = ctx.message.mentions[0]

    react_message = None
    async for channel_message in ctx.channel.history(limit=SEARCH_LIMIT):
        if (
            channel_message.author == react_user
            and not channel_message.content.startswith(f"{COMMAND_PREFIX}")
        ):
            react_message = channel_message
            break
    if not react_message:
        await priv_response(ctx, f"No valid messages found to react to!")
        return

    emoji_list = emoji_reaction_from_string(message)
    if not emoji_list:
        await priv_response(
            ctx, "Invalid message! Make sure there are no repeat letters!"
        )
        return

    for emoji_ in emoji_list:
        await react_message.add_reaction(emoji_)
