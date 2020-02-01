import requests
from discord.ext import commands

from utils.helpers import get_env_value, priv_response, tagged_response


def setup(bot):
    bot.add_command(google)
    bot.add_command(youtube)


def get_items(url, data):
    return requests.get(url, params=data).json().get("items")


@commands.command(
    name="g",
    brief="Googles that for you",
    description=(
        "Returns the top Google search result of the given search terms."
        " Returns nothing if one is not found."
    ),
    usage="[search-terms]",
    help="\nLimitations: Mentions should not be used.",
)
async def google(ctx, *args):
    if not CSE_ID or not DEV_KEY:
        await priv_response(ctx, "Sorry, I don't have the Google API keys!")
        return

    args = " ".join(args)
    items = get_items(GOOGLE_URL, data={"cx": CSE_ID, "q": args, "key": DEV_KEY})

    if not items:
        await priv_response(ctx, f"No search results found for: *{args}*")
        return

    await tagged_response(ctx, items[0].get("link"))


@commands.command(
    name="yt",
    brief="Returns top YouTube video result of search terms",
    description=(
        "Returns the top YouTube video result of the given search terms."
        " Returns nothing if one is not found."
    ),
    usage="[search-terms]",
    help="\nLimitations: Mentions should not be used.",
)
async def youtube(ctx, *args):
    if not DEV_KEY:
        await priv_response(ctx, "Sorry, I don't have the Google dev key!")
        return

    args = " ".join(args)
    items = get_items(YOUTUBE_URL, data={"q": args, "key": DEV_KEY, "type": "video"})

    if not items:
        await priv_response(ctx, f"No video results found for: *{args}*")
        return

    video_id = items[0].get("id", {}).get("videoId")
    link = f"http://youtu.be/{video_id}"

    await tagged_response(ctx, link)


CSE_ID = get_env_value("GOOGLE_CSE_ID", raise_exception=False)
DEV_KEY = get_env_value("GOOGLE_DEV_KEY", raise_exception=False)
GOOGLE_URL = "https://www.googleapis.com/customsearch/v1"
YOUTUBE_URL = "https://www.googleapis.com/youtube/v3/search?part=id&maxResults=1"
