import json

import requests
from discord.ext import commands

from utils.helpers import tagged_response


def setup(bot):
    bot.add_command(urban)


@commands.command(name="urb")
async def urban(ctx, *args):
    arg = " ".join(args).lower().strip()
    definitions = requests.get(f"{BASE_URL}{arg}").json().get("list")

    if not definitions:
        await tagged_response(ctx, f"No results found for: *{arg}*")
        return

    message = (
        definitions[0]
        .get("definition")
        .replace("[", "")
        .replace("]", "")
        .replace("\n", "")
    )
    await tagged_response(
        ctx,
        f'*{message}* ... (See more results: {SEE_MORE_URL}{arg.replace(" ","%20")})',
    )


BASE_URL = "http://api.urbandictionary.com/v0/define?term="
SEE_MORE_URL = "https://www.urbandictionary.com/define.php?term="
