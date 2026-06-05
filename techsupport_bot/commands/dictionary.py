"""Module for the dictionary extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from core import auxiliary, cogs
from discord import app_commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the dictionary plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.dictionary:
            raise AttributeError("Dictionary was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError(
            "Dictionary was not loaded due to missing API key"
        ) from exc

    await bot.add_cog(Dictionary(bot=bot))


class Dictionary(cogs.BaseCog):
    """The class for the dictionary command

    Attributes:
        DICT_API_URL (str): The URL for the dict API
    """

    DICT_API_URL: str = (
        "https://www.dictionaryapi.com/api/v3/references/collegiate/json/{}?key={}"
    )

    @app_commands.command(
        name="dictionary",
        description="Looks up a word in the dictionary",
        extras={"module": "dictionary"},
    )
    async def dictionary_lookup(
        self: Self, interaction: discord.Interaction, word: str
    ) -> None:
        """This calls the dictionary API and sends the definitions

        Args:
            interaction (discord.Interaction): The interaction that called this command
            word (str): The word to lookup in the dictionary
        """
        await interaction.response.defer()
        url = self.DICT_API_URL.format(
            word, self.bot.file_config.api.api_keys.dictionary
        )
        response = await self.bot.http_functions.http_call("get", url)
        if not response:
            embed = auxiliary.prepare_deny_embed(
                f"I could not find any definition for {word}"
            )
            await interaction.followup.send(embed=embed)
            return

        definition = response[0].shortdef

        embed = discord.Embed(title=f"Definition of {word}")
        embed.color = discord.Color.orange()
        embed.description = "\n".join(f"- {string}" for string in definition)

        await interaction.followup.send(embed=embed)
