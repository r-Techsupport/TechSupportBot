from random import randint, shuffle

from cogs import HttpPlugin, LoopPlugin
from utils.helpers import get_env_value
from utils.logger import get_logger

log = get_logger("News Plugin")


def setup(bot):
    bot.add_cog(News(bot))


class News(LoopPlugin, HttpPlugin):

    CRON_CONFIG = get_env_value("NEWS_CRON", raise_exception=False).replace('"', "")
    CHANNEL_ID = get_env_value("NEWS_CHANNEL")
    API_URL = "http://newsapi.org/v2/top-headlines?apiKey={}&country={}"
    API_KEY = get_env_value("NEWS_API_KEY")
    COUTNRY = get_env_value("NEWS_COUNTRY", raise_exception=False).upper() or "US"
    PREFER_SRCS = get_env_value("NEWS_PREFER").split(",")

    async def loop_preconfig(self):
        if not self.PREFER_SRCS:
            raise RuntimeError("No news sources were provided")
        self.channel = self.bot.get_channel(int(self.CHANNEL_ID))
        if not self.channel:
            raise RuntimeError("Unable to get channel for News plugin")
        await self.wait()

    async def execute(self):
        response = await self.http_call(
            "get", self.API_URL.format(self.API_KEY, self.COUTNRY)
        )
        response_json = response.json() if response else None

        if not response_json:
            log.warning("Unable to retrieve response from API")
            return

        articles = response_json.get("articles")
        if not articles:
            log.warning("Unable to retrieve articles from API response")
            return

        shuffle(self.PREFER_SRCS)
        shuffle(articles)
        for article in articles:
            source = article.get("source", {}).get("name")
            if not source:
                continue

            for preference in self.PREFER_SRCS:
                if preference.lower() in source.lower():
                    url = article.get("url")
                    if not url:
                        continue
                    log.debug(f"Sending News article: {url}")
                    await self.channel.send(url)
                    return

        log.warning("Unable to find article for sending")
