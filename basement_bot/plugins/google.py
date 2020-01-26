import requests
from discord.ext import commands

from utils.helpers import get_env_value, tagged_response


def setup(bot):
    bot.add_command(google)


@commands.command(name="g")
async def google(ctx, *args):
    if not CSE_ID or not DEV_KEY:
        await tagged_response(ctx, "Looks like I'm missing some API keys. RIP!")
        return

    args = " ".join(args)
    parsed = (
        requests.get(API_URL, params={"cx": CSE_ID, "q": args, "key": DEV_KEY})
        .json()
        .get("items")
    )

    if not parsed:
        await tagged_response(ctx, f"No results found for: *{args}*")
        return

    await tagged_response(ctx, parsed[0].get("link"))


CSE_ID = get_env_value("GOOGLE_CSE_ID", raise_exception=False)
DEV_KEY = get_env_value("GOOGLE_DEV_KEY", raise_exception=False)
API_URL = "https://www.googleapis.com/customsearch/v1"
