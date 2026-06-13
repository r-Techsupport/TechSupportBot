"""Module for the animal extension for the discord bot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import aiohttp
import discord
from discord import app_commands

from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the animals plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

    await bot.add_cog(Animals(bot=bot))


class Animals(cogs.BaseCog):
    """The class for the animals commands"""

    async def preconfig(self: Self) -> None:
        """This sets up the VALID_ANIMALS map to connect animal names to functions"""
        self.VALID_ANIMALS: dict[str, callable] = {
            "cat": self.get_cat,
            "dog": self.get_dog,
            "fox": self.get_fox,
            "frog": self.get_frog,
        }

    @app_commands.command(
        name="animal",
        description="Gets an animal of a given type and sends it in the channel",
    )
    async def get_animal(
        self: Self, interaction: discord.Interaction, type_of_animal: str
    ) -> None:
        """The get animal function, allowing any type of configured animal to be called

        Args:
            interaction (discord.Interaction): The interaction that called this command
            type_of_animal (str): The type of animal to get
        """
        type_of_animal = type_of_animal.lower()
        if not self.is_animal_valid(type_of_animal):
            embed = auxiliary.prepare_deny_embed(
                f"It appears {type_of_animal} is not a valid animal type for this command"
            )
            await interaction.response.send_message(embed=embed)
            return
        await interaction.response.defer()
        function_reference = self.VALID_ANIMALS.get(type_of_animal)
        image_url = await function_reference()
        await interaction.followup.send(image_url)

    @get_animal.autocomplete("type_of_animal")
    async def status_autocomplete(
        self: Self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """This builds a list of valid animal types and displays the choices to the user

        Args:
            interaction (discord.Interaction): The interaction that is calling the /animal command
            current (str): The current string in the type parameter

        Returns:
            list[app_commands.Choice[str]]: A list of currently valid choices
        """
        return [
            app_commands.Choice(name=animal, value=animal)
            for animal in self.VALID_ANIMALS
            if current.lower() in animal.lower()
        ][:10]

    def is_animal_valid(self: Self, animal: str) -> bool:
        """Checks if the passed animal parameter is valid

        Args:
            animal (str): The animal parameter to check

        Returns:
            bool: Whether its a valid animal paramter or not
        """
        return animal in self.VALID_ANIMALS

    async def get_cat(self: Self) -> str:
        """This gets the URL to an image of a cat

        Returns:
            str: The image of a cat of display
        """
        api_url: str = "https://api.thecatapi.com/v1/images/search?limit=1&api_key={}"
        url = api_url.format(
            self.bot.file_config.api.api_keys.cat,
        )
        response = await self.bot.http_functions.http_call("get", url)
        return response[0].url

    async def get_dog(self: Self) -> str:
        """This gets the URL to an image of a dog

        Returns:
            str: The image of a dog of display
        """
        api_url: str = "https://dog.ceo/api/breeds/image/random"
        response = await self.bot.http_functions.http_call("get", api_url)
        return response.message

    async def get_fox(self: Self) -> str:
        """This gets the URL to an image of a fox

        Returns:
            str: The image of a fox of display
        """
        api_url: str = "https://randomfox.ca/floof/"
        response = await self.bot.http_functions.http_call("get", api_url)
        return response.image

    async def get_frog(self: Self) -> str:
        """This gets the URL to an image of a frog

        Returns:
            str: The image of a frog of display
        """
        api_url = "https://frogs.media/api/random"

        response = await self.bot.http_functions.http_call(
            "get",
            api_url,
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(
                response.url,
                allow_redirects=False,
            ) as response_two:
                return response_two.headers.get("Location")
