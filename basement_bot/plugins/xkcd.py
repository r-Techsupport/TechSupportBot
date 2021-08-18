import random

import base
import discord
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[XKCD])


class XKCD(base.BaseCog):

    MOST_RECENT_API_URL = "https://xkcd.com/info.0.json"
    SPECIFIC_API_URL = "https://xkcd.com/%s/info.0.json"

    @commands.group(
        brief="Executes a xkcd command",
        description="Executes a xkcd command",
    )
    async def xkcd(self, ctx):
        pass

    @xkcd.command(
        name="random",
        brief="Gets a random XKCD comic",
        description="Gets a random XKCD comic",
    )
    async def random_comic(self, ctx):
        most_recent_comic_data = await self.api_call()
        if most_recent_comic_data.status_code != 200:
            await self.bot.send_with_mention(
                ctx, "I had trouble looking up XKCD's comics"
            )
            return

        max_number = most_recent_comic_data.get("num")
        if not max_number:
            await self.bot.send_with_mention(
                ctx, "I could not determine the max XKCD number"
            )
            return

        comic_number = random.randint(1, max_number)

        random_comic_data = await self.api_call(number=comic_number)
        if random_comic_data.status_code != 200:
            await self.bot.send_with_mention(
                ctx, f"I had trouble calling a random comic (#{comic_number})"
            )
            return

        embed = self.generate_embed(random_comic_data)
        if not embed:
            await self.bot.send_with_mention(
                ctx, f"I had trouble calling getting the correct XKCD info"
            )
            return

        await self.bot.send_with_mention(ctx, embed=embed)

    @xkcd.command(
        name="number",
        aliases=["#"],
        brief="Gets a XKCD comic",
        description="Gets a XKCD comic by number",
        usage="[number]",
    )
    async def numbered_comic(self, ctx, number: int):
        comic_data = await self.api_call(number=number)
        if comic_data.status_code != 200:
            await self.bot.send_with_mention(
                ctx, "I had trouble looking up XKCD's comics"
            )
            return

        embed = self.generate_embed(comic_data)
        if not embed:
            await self.bot.send_with_mention(
                ctx, f"I had trouble calling getting the correct XKCD info"
            )
            return

        await self.bot.send_with_mention(ctx, embed=embed)

    async def api_call(self, number=None):
        url = self.SPECIFIC_API_URL % (number) if number else self.MOST_RECENT_API_URL
        response = await self.bot.http_call("get", url)

        return response

    def generate_embed(self, comic_data):
        num = comic_data.get("num")
        image_url = comic_data.get("img")
        title = comic_data.get("safe_title")
        alt_text = comic_data.get("alt")

        if not all([num, image_url, title, alt_text]):
            return None

        embed = discord.Embed(title=title, description=f"https://xkcd.com/{num}")
        embed.set_author(name=f"XKCD #{num}")
        embed.set_image(url=image_url)
        embed.set_footer(text=alt_text)

        return embed
