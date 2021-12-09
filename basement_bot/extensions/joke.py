import base
import discord
import util
from discord.ext import commands


def setup(bot):
    config = bot.ExtensionConfig()
    config.add(
        key="pc_jokes",
        datatype="bool",
        title="Politically correct jokes only",
        description="True if only politically correct jokes should be shown (non-racist/non-sexist)",
        default=True,
    )
    bot.add_cog(Joker(bot=bot))
    bot.add_extension_config("joke", config)


class Joker(base.BaseCog):

    API_URL = "https://v2.jokeapi.dev/joke/Any"

    async def call_api(self, ctx, config):
        url = self.build_url(ctx, config)
        response = await util.http_call("get", url, get_raw_response=True)
        return response

    def build_url(self, ctx, config):
        blacklist_flags = []
        if not ctx.channel.is_nsfw():
            blacklist_flags.extend(["explicit", "nsfw"])
        if config.extensions.joke.pc_jokes.value:
            blacklist_flags.extend(["sexist", "racist", "religious"])
        blacklists = ",".join(blacklist_flags)

        url = f"{self.API_URL}?blacklistFlags={blacklists}&format=txt"

        return url

    def generate_embed(self, joke_text):
        embed = discord.Embed(description=joke_text)
        embed.set_author(name="Joke", icon_url=self.bot.user.avatar_url)
        embed.color = discord.Color.random()
        return embed

    @util.with_typing
    @commands.command(
        name="joke",
        brief="Tells a joke",
        description="Tells a random joke",
        usage="",
    )
    async def joke(self, ctx):
        config = await self.bot.get_context_config(ctx)
        response = await self.call_api(ctx, config)
        text = await response.text()
        embed = self.generate_embed(text)
        await util.send_with_mention(ctx, embed=embed)
