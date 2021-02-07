import random

import cogs


def setup(bot):
    bot.add_cog(News(bot))


class News(cogs.LoopPlugin):

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
            return

        random.shuffle(self.config.prefer)
        random.shuffle(articles)
        for article in articles:
            source = article.get("source", {}).get("name")
            if not source:
                continue

            for preference in self.config.prefer:
                if preference.lower() in source.lower():
                    url = article.get("url")
                    if not url:
                        continue
                    await self.channel.send(url)
                    return
