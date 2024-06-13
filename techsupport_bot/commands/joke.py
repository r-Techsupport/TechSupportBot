"""Module for the joke extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
import munch
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Joke plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="pc_jokes",
        datatype="bool",
        title="Politically correct jokes only",
        description=(
            "True only politically correct jokes should be shown"
            " (non-racist/non-sexist)"
        ),
        default=True,
    )
    await bot.add_cog(Joker(bot=bot))
    bot.add_extension_config("joke", config)


class Joker(cogs.BaseCog):
    """Class to make up the joke extension.

    Attrs:
        API_URL (str): The joke API URL

    """

    API_URL = "https://v2.jokeapi.dev/joke/Any"

    async def call_api(
        self: Self, ctx: commands.Context, config: munch.Munch
    ) -> munch.Munch:
        """Calls the joke API and returns the raw response

        Args:
            ctx (commands.Context): The context in which the joke command was run in
            config (munch.Munch): The guild config for the guild where the joke command was run

        Returns:
            munch.Munch: The reply from the API
        """
        url = self.build_url(ctx, config)
        response = await self.bot.http_functions.http_call(
            "get", url, get_raw_response=True
        )
        return response

    def build_url(self: Self, ctx: commands.Context, config: munch.Munch) -> str:
        """Builds the API URL based on exclusions of categories
        Will exclude NSFW jokes if the channel isn't NSFW
        Will exclude offensive jokes if the PC jokes config is enabled

        Args:
            ctx (commands.Context): The context in which the original joke command was run in
            config (munch.Munch): The config for the guild where the original command was run

        Returns:
            str: The URL, properly formatted and ready to be called
        """
        blacklist_flags = []
        if not ctx.channel.is_nsfw():
            blacklist_flags.extend(["explicit", "nsfw"])
        if config.extensions.joke.pc_jokes.value:
            blacklist_flags.extend(["sexist", "racist", "religious"])
        blacklists = ",".join(blacklist_flags)

        url = f"{self.API_URL}?blacklistFlags={blacklists}&format=txt"

        return url

    def generate_embed(self: Self, joke_text: str) -> discord.Embed:
        """Makes a fancy embed showing the joke recieved from the API

        Args:
            joke_text (str): The raw text of the joke from the API

        Returns:
            discord.Embed: The formatted embed, ready to bt sent
        """
        embed = discord.Embed(description=joke_text)
        embed.set_author(name="Joke", icon_url=self.bot.user.display_avatar.url)
        embed.color = discord.Color.random()
        return embed

    @auxiliary.with_typing
    @commands.command(
        name="joke",
        brief="Tells a joke",
        description="Tells a random joke",
        usage="",
    )
    async def joke(self: Self, ctx: commands.Context) -> None:
        """Discord entry point for the joke command
        This will get a joke and send it in the channel the command was called in

        Args:
            ctx (commands.Context): The context in which the command was run in
        """
        config = self.bot.guild_configs[str(ctx.guild.id)]
        response = await self.call_api(ctx, config)
        text = response["text"]
        embed = self.generate_embed(text)
        await ctx.send(embed=embed)
