from __future__ import annotations

import random
from typing import TYPE_CHECKING

import flickrapi
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the flickr plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """

    await bot.add_cog(Flickr(bot=bot))


class Flickr(cogs.BaseCog):
    """Class handling the animal search functionality."""

    @auxiliary.with_typing
    @commands.command(
        name="flickr",
        brief="Gets an animal",
        description="Gets an animal",
        aliases=["animal"],
    )
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def flickr(self, ctx: commands.Context, *, animal: str = "animal") -> None:
        """Fetches and displays an animal image from Flickr."""
        if ctx.author.guild_permissions.administrator:
            Flickr.flickr.reset_cooldown(ctx)

        flickrAPI = flickrapi.FlickrAPI(
            ctx.bot.file_config.api.api_keys.flickr_api_key.encode("utf-8"),
            ctx.bot.file_config.api.api_keys.flicker_api_secret.encode("utf-8"),
            cache=True,
        )

        try:
            initial_search = flickrAPI.photos.search(
                text=animal,
                tags=f"{animal}, -person, -people, -portrait, -selfie, -human",
                tag_mode="all",
                extras="url_c",
                per_page=1,
                format="parsed-json",
                content_type=1,
                safe_search=1,
                sort="relevance",
            )
            total_pages = initial_search["photos"]["pages"]
            max_pages_to_check = min(total_pages, 1000)

            for _ in range(10):
                random_page = (
                    random.randint(1, max_pages_to_check)
                    if max_pages_to_check > 1
                    else 1
                )
                photos = flickrAPI.photos.search(
                    text=animal,
                    tags=f"{animal}, -person, -people, -portrait, -selfie, -human",
                    tag_mode="all",
                    extras="url_c",
                    per_page=1,
                    page=random_page,
                    format="parsed-json",
                    content_type=1,
                    safe_search=1,
                    sort="relevance",
                    license="4,6,7,9",
                    media="photos",
                )

                photo_list = photos.get("photos", {}).get("photo", [])
                photo_with_url = next(
                    (photo for photo in photo_list if "url_c" in photo), None
                )
                if photo_with_url:
                    await ctx.send(photo_with_url["url_c"])
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
