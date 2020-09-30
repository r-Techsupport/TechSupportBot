from discord.ext import commands

from cogs import BasicPlugin
from utils.helpers import embed_from_kwargs


def setup(bot):
    bot.add_cog(Embedder(bot))


class Embedder(BasicPlugin):

    PLUGIN_NAME = "Embedder"
    HAS_CONFIG = False

    @commands.command(name="embed", brief="", description="", usage="")
    async def embed(self, ctx):
        await ctx.send(embed=embed_from_kwargs("Test", "Test", **{"Hello": "World"}))
