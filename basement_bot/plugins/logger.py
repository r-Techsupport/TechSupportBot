from cogs import MatchPlugin
from discord import Embed


def setup(bot):
    bot.add_cog(Logger(bot))


class Logger(MatchPlugin):

    PLUGIN_NAME = __name__

    def match(self, ctx, _):
        if not ctx.channel.id in self.config.input_channels:
            return False
        return True

    async def response(self, ctx, _):
        channel = self.get_logging_channel()
        await channel.send(embed=self.generate_embed(ctx))

    def get_logging_channel(self):
        return self.bot.get_channel(self.config.output_channel)

    def generate_embed(self, ctx):
        embed = Embed(title="Logger Event")
        embed.add_field(name="Content", value=ctx.message.content[:256], inline=False)
        embed.add_field(name="Author", value=ctx.author.name)
        embed.add_field(name="Channel", value=ctx.channel.name)
        embed.color = self.config.embed_color
        embed.set_thumbnail(url=ctx.author.avatar_url)
        return embed
