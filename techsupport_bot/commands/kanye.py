"""Module for the kanye extension for the discord bot."""

import asyncio
import random

import discord
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands


async def setup(bot):
    """Adding the config for kanye to the config file."""
    config = extensionconfig.ExtensionConfig()
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

    await bot.add_cog(KanyeQuotes(bot=bot, extension_name="kanye"))
    bot.add_extension_config("kanye", config)


class KanyeQuotes(cogs.LoopCog):
    """Class to get the Kanye quotes from the api."""

    API_URL = "https://api.kanye.rest"
    KANYE_PICS = [
        "https://i.imgur.com/ITmTXGz.jpg",
        "https://i.imgur.com/o8BkPrL.jpg",
        "https://i.imgur.com/sA5qP3F.jpg",
        "https://i.imgur.com/1fX29Y3.jpg",
        "https://i.imgur.com/g1o2Gro.jpg",
    ]

    def generate_themed_embed(self, quote: str) -> discord.Embed:
        """Generates a themed embed for the kayne plugin
        Includes adding the quote, changing the color, and adding an icon

        Args:
            quote (str): The quote to put in the embed

        Returns:
            discord.Embed: The formatted embed, ready to be sent
        """
        embed = auxiliary.generate_basic_embed(
            title=f'"{quote}"',
            description="Kanye West",
            color=discord.Color.dark_gold(),
            url=random.choice(self.KANYE_PICS),
        )
        return embed

    async def get_quote(self):
        """Method to get the quote from the api."""
        response = await self.bot.http_functions.http_call("get", self.API_URL)
        return response.get("quote")

    async def execute(self, config, guild):
        """Method to execute and give the quote to discord."""
        quote = await self.get_quote()
        embed = self.generate_themed_embed(quote=quote)

        channel = guild.get_channel(int(config.extensions.kanye.channel.value))
        if not channel:
            return

        await channel.send(embed=embed)

    async def wait(self, config, _):
        """Method to only wait a max amount of time from the api."""
        await asyncio.sleep(
            random.randint(
                config.extensions.kanye.min_wait.value * 3600,
                config.extensions.kanye.max_wait.value * 3600,
            )
        )

    @auxiliary.with_typing
    @commands.command(
        brief="Gets a Kanye West quote",
        description="Gets a random Kanye West quote from the Kanye West API",
    )
    async def kanye(self, ctx):
        """Method to call the command on discord."""
        quote = await self.get_quote()
        embed = self.generate_themed_embed(quote=quote)

        await ctx.send(embed=embed)
