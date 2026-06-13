"""Module for the news extension for the discord bot."""

from __future__ import annotations

import enum
import random
from typing import TYPE_CHECKING, Self

import aiocron
import discord
import munch
from discord import app_commands

import configuration
from botlogging import LogContext, LogLevel
from core import cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the News plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if an API key is missing to prevent unusable commands from loading
    """

    # Don't load without the API key
    try:
        if not bot.file_config.api.api_keys.news:
            raise AttributeError("News was not loaded due to missing API key")
    except AttributeError as exc:
        raise AttributeError("News was not loaded due to missing API key") from exc

    await bot.add_cog(News(bot=bot))


class Category(enum.Enum):
    """Class to set up categories for the news.

    Attributes:
        BUSINESS (str): The string representation for business
        ENTERTAINMENT (str): The string representation for entertainment
        GENERAL (str): The string representation for general
        HEALTH (str): The string representation for health
        SCIENCE (str): The string representation for science
        SPORTS (str): The string representation for sports
        TECH (str): The string representation for technology

    """

    BUSINESS: str = "business"
    ENTERTAINMENT: str = "entertainment"
    GENERAL: str = "general"
    HEALTH: str = "health"
    SCIENCE: str = "science"
    SPORTS: str = "sports"
    TECH: str = "technology"


class News(cogs.LoopCog):
    """Class to set up the news extension for the discord bot.

    Attributes:
        API_URL (str): The news API URL

    """

    API_URL: str = "http://newsapi.org/v2/top-headlines?apiKey={}&country={}"

    async def preconfig(self: Self) -> None:
        """Sets up the list of valid categories in a class wide variable"""
        self.valid_category = []
        for item in Category:
            self.valid_category.append(item.value)

    async def get_headlines(
        self: Self,
        country_code: str,
        category: str = None,
        is_interaction: bool = False,
    ) -> list[munch.Munch]:
        """Calls the API to get the list of headlines based on the category and country

        Args:
            country_code (str): The country code to get headlines from
            category (str, optional): The category of headlines to get. Defaults to None.
            is_interaction (bool): If the headline is being called from an interaction

        Returns:
            list[munch.Munch]: The list of article objects from the API
        """
        url = self.API_URL.format(
            self.bot.file_config.api.api_keys.news,
            country_code,
        )
        if category:
            url = f"{url}&category={category}"

        response = await self.bot.http_functions.http_call(
            "get", url, use_app_error=is_interaction
        )

        articles = response.get("articles")
        if not articles:
            return None
        return articles

    async def get_random_headline(
        self: Self,
        country_code: str,
        category: str = None,
        is_interaction: bool = False,
    ) -> munch.Munch:
        """Gets a single article object from the news API

        Args:
            country_code (str): The country code of the headliens to get
            category (str, optional): The category of headlines to get. Defaults to None.
            is_interaction (bool): If the headline is being called from an interaction

        Returns:
            munch.Munch: The raw API object representing a news headline
        """

        articles = await self.get_headlines(country_code, category, is_interaction)

        # Filter out articles with URLs containing "removed.com"
        filtered_articles = []
        for article in articles:
            url = article.get("url", "")
            if url != "https://removed.com":
                filtered_articles.append(article)

        # Check if there are any articles left after filtering
        if not filtered_articles:
            return None

        # Choose a random article from the filtered list
        return random.choice(filtered_articles)

    async def execute(self: Self, guild: discord.Guild) -> None:
        """Loop entry point for the news command
        If a channel is configured to loop news headlines, this will execute that

        Args:
            guild (discord.Guild): The guild where the loop is running
        """
        channel = guild.get_channel(
            int(configuration.get_config_entry(guild.id, "news_channel"))
        )
        if not channel:
            return

        url = None
        while not url:
            article = await self.get_random_headline(
                configuration.get_config_entry(guild.id, "news_country"),
                Category(
                    configuration.get_config_entry(guild.id, "news_category")
                ).value,
            )
            url = article.get("url")

        if article is None:
            return

        log_channel = configuration.get_config_entry(guild.id, "core_logging_channel")
        await self.bot.logger.send_log(
            message=f"Sending news headline to #{channel.name}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild, channel=channel),
            channel=log_channel,
        )
        if url.endswith("/"):
            url = url[:-1]
        await channel.send(url)

    async def wait(self: Self, guild: discord.Guild) -> None:
        """Waits the defined time set for the loop, based on the cronjob

        Args:
            guild (discord.Guild): The guild where the loop will occur
        """
        await aiocron.crontab(
            configuration.get_config_entry(guild.id, "news_cron_config")
        ).next()

    @app_commands.command(
        name="news",
        description="Gets a random news headline",
    )
    async def news_command(
        self: Self, interaction: discord.Interaction, category: str = ""
    ) -> None:
        """Discord command entry point for getting a news article

        Args:
            interaction (discord.Interaction): The interaction in which the command was run
            category (str, optional): The category to get news headlines from. Defaults to None.
        """
        if category is None or category.lower() not in self.valid_category:
            category = random.choice(list(Category)).value
        else:
            category.lower()

        url = None
        while not url:
            article = await self.get_random_headline(
                configuration.get_config_entry(interaction.guild.id, "news_country"),
                category,
                True,
            )
            url = article.get("url")

        if article is None:
            return

        if url.endswith("/"):
            url = url[:-1]

        await interaction.response.send_message(content=url)

        # Log the command execution
        log_channel = configuration.get_config_entry(
            interaction.guild.id, "core_logging_channel"
        )
        if log_channel:
            await self.bot.logger.send_log(
                message=(
                    f"News command executed: "
                    f"Sent a news headline to {interaction.channel.name}"
                ),
                level=LogLevel.INFO,
                context=LogContext(
                    guild=interaction.guild, channel=interaction.channel
                ),
                channel=log_channel,
            )

    @news_command.autocomplete("category")
    async def news_autocompletion(
        self: Self, interaction: discord.Interaction, current: str
    ) -> list:
        """This command creates a list of categories for autocomplete the news command.

        Args:
            interaction (discord.Interaction): The interaction that started the command
            current (str): The current input from the user.

        Returns:
            list: The list of autocomplete for the news command.
        """
        news_category = []
        for category in Category:
            if current.lower() in category.value.lower():
                news_category.append(
                    app_commands.Choice(name=category.value, value=category.value)
                )
        return news_category
