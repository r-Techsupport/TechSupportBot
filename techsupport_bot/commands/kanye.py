"""Module for the kanye extension for the discord bot."""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Self

import discord
import munch
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Kanye plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
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
    """Class to get the Kanye quotes from the api.

    Attrs:
        API_URL (str): The Kanye API URL
        KANYE_PICS (list[str]): The list of Kanye pics to pick from randomly
    """

    API_URL = "https://api.kanye.rest"
    KANYE_PICS = [
        "https://i.imgur.com/ITmTXGz.jpg",
        "https://i.imgur.com/o8BkPrL.jpg",
        "https://i.imgur.com/sA5qP3F.jpg",
        "https://i.imgur.com/1fX29Y3.jpg",
        "https://i.imgur.com/g1o2Gro.jpg",
    ]

    def generate_themed_embed(self: Self, quote: str) -> discord.Embed:
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

    async def get_quote(self: Self) -> str:
        """Calls the kanye API to get a quote, returns just the quote from the response

        Returns:
            str: The raw quote from the API, without any special formatting
        """
        response = await self.bot.http_functions.http_call("get", self.API_URL)
        return response.get("quote")

    async def execute(self: Self, config: munch.Munch, guild: discord.Guild) -> None:
        """The main entry point for the loop for kanye
        This is executed automatically and shouldn't be called manually

        Args:
            config (munch.Munch): The guild config where the loop is taking place
            guild (discord.Guild): The guild where the loop is taking place
        """
        quote = await self.get_quote()
        embed = self.generate_themed_embed(quote=quote)

        channel = guild.get_channel(int(config.extensions.kanye.channel.value))
        if not channel:
            return

        await channel.send(embed=embed)

    async def wait(self: Self, config: munch.Munch, _: discord.Guild) -> None:
        """This sleeps a random amount of time between Kanye quotes

        Args:
            config (munch.Munch): The guild config where the loop is taking place
        """
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
    async def kanye(self: Self, ctx: commands.Context) -> None:
        """Entry point and logic for the .kanye discord command
        This allows for printing of a Kanye quote outside of the loop

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        quote = await self.get_quote()
        embed = self.generate_themed_embed(quote=quote)

        await ctx.send(embed=embed)
