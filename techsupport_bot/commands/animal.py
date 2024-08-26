"""Module for the animal extension for the discord bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import flickrapi
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the animals plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

    await bot.add_cog(Animals(bot=bot))


class Animals(cogs.BaseCog):
    """The class for the animals commands

    Attrs:
        CAT_API_URL (str): The URL for the cat API
        DOG_API_URL (str): The URL for the dog API
        FOX_API_URL (str): The URL for the fox API
        FROG_API_URL (str): The URL for the frog API
        FLICKR_API_URL (str): The URL for the animal API
    """

    CAT_API_URL = "https://api.thecatapi.com/v1/images/search?limit=1&api_key={}"
    DOG_API_URL = "https://dog.ceo/api/breeds/image/random"
    FOX_API_URL = "https://randomfox.ca/floof/"
    FROG_API_URL = "https://frogs.media/api/random"
    FLICKR_API_URL = "https://api.flickr.com/services/rest/"

    @auxiliary.with_typing
    @commands.command(name="cat", brief="Gets a cat", description="Gets a cat")
    async def cat(self: Self, ctx: commands.Context) -> None:
        """Prints a cat to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        if not self.bot.file_config.api.api_keys.cat:
            embed = auxiliary.prepare_deny_embed(
                "No cat API has been set, so not cat can be shown"
            )
            await ctx.send(embed=embed)
            return

        url = self.CAT_API_URL.format(
            self.bot.file_config.api.api_keys.cat,
        )
        response = await self.bot.http_functions.http_call("get", url)
        await ctx.send(response[0].url)

    @auxiliary.with_typing
    @commands.command(name="dog", brief="Gets a dog", description="Gets a dog")
    async def dog(self: Self, ctx: commands.Context) -> None:
        """Prints a dog to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.DOG_API_URL)
        await ctx.send(response.message)

    @auxiliary.with_typing
    @commands.command(name="frog", brief="Gets a frog", description="Gets a frog")
    async def frog(self: Self, ctx: commands.Context) -> None:
        """Prints a frog to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.FROG_API_URL)
        await ctx.send(response.url)

    @auxiliary.with_typing
    @commands.command(name="fox", brief="Gets a fox", description="Gets a fox")
    async def fox(self: Self, ctx: commands.Context) -> None:
        """Prints a fox to discord

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        response = await self.bot.http_functions.http_call("get", self.FOX_API_URL)
        await ctx.send(response.image)

    @auxiliary.with_typing
    @commands.command(
        name="animal", brief="Gets an animal", description="Gets an animal"
    )
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def animal(self, ctx: commands.Context, *, animal: str = "animal") -> None:
        """Prints an animal to discord

        Args:
            self (Self): Self
            ctx (commands.Context): The context in which the command was run
            animal (str): The animal to search for
        """
        # Check if the user is an admin, and if so, reset the cooldown
        if ctx.author.guild_permissions.administrator:
            self.animal.reset_cooldown(ctx)
          
        flickr = flickrapi.FlickrAPI(
            self.bot.file_config.api.api_keys.flickr_api_key.encode("utf-8"),
            self.bot.file_config.api.api_keys.flicker_api_secret.encode("utf-8"),
            cache=True,
        )

        try:
            # Perform the initial search to get the total number of pages
            initial_search = flickr.photos.search(
                text=animal,
                tags=f"{animal}, -person, -people, -portrait, -selfie, -human",
                tag_mode="all",
                extras="url_c",
                per_page=1,
                format="parsed-json",
                content_type=1,  # 1 for photos only
                safe_search=1,  # 1 for safe search
                sort="relevance",
            )
            total_pages = initial_search["photos"]["pages"]
            print(f"Flickr: {initial_search}")
            # Limit the number of pages to a reasonable subset (e.g., 1000)
            max_pages_to_check = min(total_pages, 1000)

            for _ in range(10):
                if max_pages_to_check > 1:
                    random_page = random.randint(1, max_pages_to_check)
                else:
                    random_page = 1

                # Perform the search on the random page
                photos = flickr.photos.search(
                    text=animal,
                    tags=f"{animal}, -person, -people, -portrait, -selfie, -human",
                    tag_mode="all",
                    extras="url_c",
                    per_page=1,
                    page=random_page,
                    format="parsed-json",
                    content_type=1,  # 1 for photos only
                    safe_search=1,  # 1 for safe search
                    sort="relevance",  
                    license="4,6,7,9", # filter by free and public domain licenses
                    media="photos",
                )

                # Extract the URL of the first photo on the random page
                photo_list = photos.get("photos", {}).get("photo", [])
                if not photo_list:
                    continue

                # Filter photos that have the 'url_c' attribute
                photo_with_url = next(
                    (photo for photo in photo_list if "url_c" in photo), None
                )
                if not photo_with_url:
                    continue

                photo_url = photo_with_url["url_c"]
                if not photo_url:
                    continue

                await ctx.send(photo_url)
                return

            await auxiliary.send_deny_embed(
                message=f"No suitable {animal} photos found.",
                channel=ctx.channel,
            )

        except flickrapi.exceptions.FlickrError as e:
            await ctx.send(
                f"An error occurred while fetching data from Flickr: {str(e)}. Please try again later."
            )
            
        except Exception as e:
            await ctx.send(
                f"An unexpected error occurred: {str(e)}. The issue has been logged."
            )
