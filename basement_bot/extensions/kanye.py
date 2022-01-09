import asyncio
import random

import base
import discord
import util
from discord.ext import commands


def setup(bot):
    config = bot.ExtensionConfig()
    config.add(
        key="channel",
        datatype="int",
        title="Kanye Channel ID",
        description="The ID of the channel the Kanye West quote should appear in",
        default=None,
    )
    config.add(
        key="min_wait",
        datatype="int",
        title="Min wait (hours)",
        description="The minimum number of hours to wait between Kanye events",
        default=24,
    )
    config.add(
        key="max_wait",
        datatype="int",
        title="Max wait (hours)",
        description="The minimum number of hours to wait between Kanye events",
        default=48,
    )

    bot.add_cog(KanyeQuotes(bot=bot, extension_name="kanye"))
    bot.add_extension_config("kanye", config)


class KanyeEmbed(discord.Embed):

    KANYE_PICS = [
        "https://i.imgur.com/ITmTXGz.jpg",
        "https://i.imgur.com/o8BkPrL.jpg",
        "https://i.imgur.com/sA5qP3F.jpg",
        "https://i.imgur.com/1fX29Y3.jpg",
        "https://i.imgur.com/g1o2Gro.jpg",
    ]

    def __init__(self, *args, **kwargs):
        quote = kwargs.pop("quote")
        super().__init__(*args, **kwargs)
        self.set_thumbnail(url=random.choice(self.KANYE_PICS))
        self.color = discord.Color.dark_gold()
        self.title = f'"{quote}"'
        self.description = "Kanye West"


class KanyeQuotes(base.LoopCog):

    API_URL = "https://api.kanye.rest"

    async def get_quote(self):
        response = await self.bot.http_call("get", self.API_URL)
        return response.get("quote")

    async def execute(self, config, guild):
        quote = await self.get_quote()
        embed = KanyeEmbed(quote=quote)

        channel = guild.get_channel(int(config.extensions.kanye.channel.value))
        if not channel:
            return

        await channel.send(embed=embed)

    async def wait(self, config, _):
        await asyncio.sleep(
            random.randint(
                config.extensions.kanye.min_wait.value * 3600,
                config.extensions.kanye.max_wait.value * 3600,
            )
        )

    @util.with_typing
    @commands.guild_only()
    @commands.command(
        brief="Gets a Kanye West quote",
        description="Gets a random Kanye West quote from the Kanye West API",
    )
    async def kanye(self, ctx):
        quote = await self.get_quote()
        embed = KanyeEmbed(quote=quote)

        await ctx.send(embed=embed)
