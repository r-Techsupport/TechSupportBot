"""Module for the joke extension for the discord bot."""
import base
import discord
import util
from discord.ext import commands


async def setup(bot):
    """Method to add the joke extension to the config file."""
    config = bot.ExtensionConfig()
    config.add(
        key="pc_jokes",
        datatype="bool",
        title="Politically correct jokes only",
        description=(
            "True only politically correct jokes should be shown"
            " (non-racist/non-sexist)"
        ),
        default=True,
    )
    await bot.add_cog(Joker(bot=bot))
    bot.add_extension_config("joke", config)


class Joker(base.BaseCog):
    """Class to make up the joke extension."""

    API_URL = "https://v2.jokeapi.dev/joke/Any"

    async def call_api(self, ctx, config):
        """Method to call the api to get the joke from."""
        url = self.build_url(ctx, config)
        response = await self.bot.http_call("get", url, get_raw_response=True)
        return response

    def build_url(self, ctx, config):
        """Method to filter out non-wanted jokes."""
        blacklist_flags = []
        if not ctx.channel.is_nsfw():
            blacklist_flags.extend(["explicit", "nsfw"])
        if config.extensions.joke.pc_jokes.value:
            blacklist_flags.extend(["sexist", "racist", "religious"])
        blacklists = ",".join(blacklist_flags)

        url = f"{self.API_URL}?blacklistFlags={blacklists}&format=txt"

        return url

    def generate_embed(self, joke_text):
        """Method to generate the embed to send to discord for displaying joke."""
        embed = discord.Embed(description=joke_text)
        embed.set_author(name="Joke", icon_url=self.bot.user.display_avatar.url)
        embed.color = discord.Color.random()
        return embed

    @util.with_typing
    @commands.cooldown(1, 60, commands.BucketType.channel)
    @commands.command(
        name="joke",
        brief="Tells a joke",
        description="Tells a random joke",
        usage="",
    )
    async def joke(self, ctx):
        """Method to call to get all the joke together."""
        config = await self.bot.get_context_config(ctx)
        response = await self.call_api(ctx, config)
        text = await response.text()
        embed = self.generate_embed(text)
        await ctx.send(embed=embed)
