"""Module for the news extension for the discord bot."""

from __future__ import annotations

import enum
import random
from typing import TYPE_CHECKING

import aiocron
import discord
from botlogging import LogContext, LogLevel
from core import cogs, extensionconfig
from discord import app_commands

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

    config = extensionconfig.ExtensionConfig()
    config.add(
        key="channel",
        datatype="int",
        title="Daily News Channel ID",
        description="The ID of the channel the news should appear in",
        default=None,
    )
    config.add(
        key="cron_config",
        datatype="string",
        title="Cronjob config for news",
        description="Crontab syntax for executing news events (example: 0 17 * * *)",
        default="0 17 * * *",
    )
    config.add(
        key="country",
        datatype="string",
        title="Country code",
        description="Country code to receive news for (example: US)",
        default="US",
    )
    config.add(
        key="category",
        datatype="str",
        title="Category",
        description="The category to use when receiving cronjob headlines",
        default=None,
    )

    await bot.add_cog(News(bot=bot, extension_name="news"))
    bot.add_extension_config("news", config)


class Category(enum.Enum):
    """Class to set up categories for the news."""

    BUSINESS = "business"
    ENTERTAINMENT = "entertainment"
    GENERAL = "general"
    HEALTH = "health"
    SCIENCE = "science"
    SPORTS = "sports"
    TECH = "technology"


class News(cogs.LoopCog):
    """Class to set up the news extension for the discord bot."""

    API_URL = "http://newsapi.org/v2/top-headlines?apiKey={}&country={}"

    async def preconfig(self):
        """Function to check to see if value enter is valid."""
        self.valid_category = []
        for item in Category:
            self.valid_category.append(item.value)

    async def get_headlines(self, country_code, category=None):
        """Method to get the headline for the news command."""
        url = self.API_URL.format(
            self.bot.file_config.api.api_keys.news,
            country_code,
        )
        if category:
            url = f"{url}&category={category}"

        response = await self.bot.http_functions.http_call("get", url)

        articles = response.get("articles")
        if not articles:
            return None

        return articles

    async def get_random_headline(self, country_code, category=None):
        """Method to get a random headline for the news command."""
        articles = await self.get_headlines(country_code, category)
        # Filter out articles with URLs containing "https://removed.com"
        articles = [
            article
            for article in articles
            if not article.get("url", "").startswith("https://removed.com")
        ]
        # Check if there are any articles left after filtering
        if not articles:
            return None

        # Choose a random article from the filtered list
        return random.choice(articles)

    async def execute(self, config, guild):
        """Method to execute the news command."""
        channel = guild.get_channel(int(config.extensions.news.channel.value))
        if not channel:
            return

        url = None
        while not url:
            article = await self.get_random_headline(
                config.extensions.news.country.value,
                Category(config.extensions.news.category.value).value,
            )
            url = article.get("url")

        log_channel = config.get("logging_channel")
        await self.bot.logger.send_log(
            message=f"Sending news headline to #{channel.name}",
            level=LogLevel.INFO,
            context=LogContext(guild=guild, channel=channel),
            channel=log_channel,
        )
        if url.endswith("/"):
            url = url[:-1]
        await channel.send(url)

    async def wait(self, config, _):
        """Method to define the wait time for the news api pull."""
        await aiocron.crontab(config.extensions.news.cron_config.value).next()

    # @commands.group(
    #     brief="Executes a news command",
    #     description="Executes a news command",
    # )
    # async def news(self, ctx):
    #     """Method to set up the news command."""

    #     # Executed if there are no/invalid args supplied
    #     await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @app_commands.command(
        name="news",
        description="Gets a random news headline",
        extras={"module": "news"},
    )
    async def news_command(self, interaction: discord.Interaction, category: str = ""):
        """Method to define the random to get a news."""
        if category is None or category.lower() not in self.valid_category:
            category = random.choice(list(Category)).value
        else:
            category.lower()

        config = self.bot.guild_configs[str(interaction.guild.id)]

        url = None
        while not url:
            article = await self.get_random_headline(
                config.extensions.news.country.value, category
            )
            url = article.get("url")

        if url.endswith("/"):
            url = url[:-1]

        await interaction.response.send_message(content=url)

    @news_command.autocomplete("category")
    async def news_autocompletion(
        self, interaction: discord.Interaction, current: str
    ) -> list:
        """This command creates a list of categories for autocomplete the news command.

        Args:
            interaction (discord.Interaction): The interaction that started the command
            current (str): The current input from the user.

        Returns:
            The list of autocomplete for the news command.
        """
        news_category = []
        for category in Category:
            if current.lower() in category.value.lower():
                news_category.append(
                    app_commands.Choice(name=category.value, value=category.value)
                )
        return news_category
