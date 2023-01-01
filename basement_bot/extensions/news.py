import enum
import random

import aiocron
import base
from discord.ext import commands


def setup(bot):
    config = bot.ExtensionConfig()
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

    bot.add_cog(News(bot=bot, extension_name="news"))
    bot.add_extension_config("news", config)


class Category(enum.Enum):
    BUSINESS = "business"
    ENTERTAINMENT = "entertainment"
    GENERAL = "general"
    HEALTH = "health"
    SCIENCE = "science"
    SPORTS = "sports"
    TECH = "technology"


class News(base.LoopCog):

    API_URL = "http://newsapi.org/v2/top-headlines?apiKey={}&country={}"

    async def get_headlines(self, country_code, category=None):
        url = self.API_URL.format(
            self.bot.file_config.main.api_keys.news,
            country_code,
        )
        if category:
            url = f"{url}&category={category}"

        response = await self.bot.http_call("get", url)

        articles = response.get("articles")
        if not articles:
            return None

        return articles

    async def get_random_headline(self, country_code, category=None):
        articles = await self.get_headlines(country_code, category)
        return random.choice(articles)

    async def execute(self, config, guild):
        channel = guild.get_channel(int(config.extensions.news.channel.value))
        if not channel:
            return

        url = None
        while not url:
            article = await self.get_random_headline(
                config.extensions.news.country.value,
                config.extensions.news.category.value,
            )
            url = article.get("url")

        await self.bot.guild_log(
            guild,
            "logging_channel",
            "info",
            f"Sending news headline to #{channel.name}",
            send=True,
        )
        if url.endswith("/"):
            url = url[:-1]
        await channel.send(url)

    async def wait(self, config, _):
        await aiocron.crontab(config.extensions.news.cron_config.value).next()

    @commands.cooldown(1, 30, commands.BucketType.channel)
    @commands.group(
        brief="Executes a news command",
        description="Executes a news command",
    )
    async def news(self, ctx):
        pass

    @news.command(
        name="random",
        brief="Gets a random news article",
        description="Gets a random news headline",
        usage="[category] (optional)",
    )
    async def random(self, ctx, category: Category = None):
        config = await self.bot.get_context_config(ctx)

        url = None
        while not url:
            article = await self.get_random_headline(
                config.extensions.news.country.value, category.value
            )
            url = article.get("url")

        if url.endswith("/"):
            url = url[:-1]

        await ctx.send(content=url)
