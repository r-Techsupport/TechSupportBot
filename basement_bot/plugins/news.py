from random import shuffle

from cogs import HttpPlugin, LoopPlugin
from utils.logger import get_logger

log = get_logger("News Plugin")


def setup(bot):
    bot.add_cog(News(bot))


class News(LoopPlugin, HttpPlugin):

    PLUGIN_NAME = __name__
    API_URL = "http://newsapi.org/v2/top-headlines?apiKey={}&country={}"

    async def loop_preconfig(self):
        if not self.config.prefer:
            raise RuntimeError("No news sources were provided")

        self.channel = self.bot.get_channel(self.config.channel)
        if not self.channel:
            raise RuntimeError("Unable to get channel for News plugin")

        await self.wait()

    async def execute(self):
        response = await self.http_call(
            "get", self.API_URL.format(self.config.api_key, self.config.country)
        )

        articles = response.get("articles")
        if not articles:
            log.warning("Unable to retrieve articles from API response")
            return

        shuffle(self.config.prefer)
        shuffle(articles)
        for article in articles:
            source = article.get("source", {}).get("name")
            if not source:
                continue

            for preference in self.config.prefer:
                if preference.lower() in source.lower():
                    url = article.get("url")
                    if not url:
                        continue
                    log.debug(f"Sending News article: {url}")
                    await self.channel.send(url)
                    return

        log.warning("Unable to find article for sending")
