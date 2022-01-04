import random

import aiocron
import base
import util
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

    bot.add_cog(News(bot=bot, extension_name="news"))
    bot.add_extension_config("news", config)


class News(base.LoopCog):

    API_URL = "http://newsapi.org/v2/top-headlines?apiKey={}&country={}"

    async def get_headlines(self, config):
        response = await self.bot.http_call(
            "get",
            self.API_URL.format(
                self.bot.file_config.main.api_keys.news,
                config.extensions.news.country.value,
            ),
        )

        articles = response.get("articles")
        if not articles:
            return None

        return articles

    async def get_random_headline(self, config):
        articles = await self.get_headlines(config)
        return random.choice(articles)

    async def execute(self, config, guild):
        channel = guild.get_channel(int(config.extensions.news.channel.value))
        if not channel:
            return

        url = None
        while not url:
            article = await self.get_random_headline(config)
            url = article.get("url")

        await self.bot.guild_log(
            guild,
            "logging_channel",
            "info",
            f"Sending news headline to #{channel.name}",
            send=True,
        )
        await channel.send(url)

    async def wait(self, config, _):
        await aiocron.crontab(config.extensions.news.cron_config.value).next()

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
    )
    async def random(self, ctx):
        config = await self.bot.get_context_config(ctx)

        url = None
        while not url:
            article = await self.get_random_headline(config)
            url = article.get("url")

        await util.send_with_mention(ctx, url)
