import random

import aiocron
import base
import util


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

    async def execute(self, config, guild):
        channel = guild.get_channel(int(config.extensions.news.channel.value))
        if not channel:
            return

        response = await util.http_call(
            "get",
            self.API_URL.format(
                self.bot.file_config.main.api_keys.news,
                config.extensions.news.country.value,
            ),
        )

        articles = response.get("articles")
        if not articles:
            return

        random.shuffle(articles)

        for article in articles:
            source = article.get("source", {}).get("name")
            if not source:
                continue

            url = article.get("url")
            if not url:
                continue

            await channel.send(url)
            return

    async def wait(self, config, _):
        await aiocron.crontab(config.extensions.news.cron_config.value).next()
