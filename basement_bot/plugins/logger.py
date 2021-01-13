from cogs import MatchPlugin


def setup(bot):
    bot.add_cog(Logger(bot))


class Logger(MatchPlugin):

    PLUGIN_NAME = __name__

    async def match(self, ctx, _):
        if not ctx.channel.id in self.config.input_channels:
            return False
        return True

    async def response(self, ctx, _):
        channel = self.get_logging_channel()
        await channel.send(embed=self.generate_embed(ctx))

    def get_logging_channel(self):
        return self.bot.get_channel(self.config.output_channel)

    def generate_embed(self, ctx):
        embed = self.bot.embed_api.Embed()
        embed.add_field(
            name="Content", value=ctx.message.content or "<None>", inline=False
        )

        if ctx.message.attachments:
            embed.add_field(
                name="Attachments",
                value=" ".join(
                    attachment.url for attachment in ctx.message.attachments
                ),
            )

        embed.add_field(
            name="Channel",
            value=f"{ctx.channel.name} ({ctx.channel.mention})",
            inline=False,
        )

        embed.add_field(
            name="Display Name", value=ctx.author.display_name, inline=False
        )

        embed.add_field(name="Name", value=ctx.author.name, inline=False)

        embed.add_field(
            name="Discriminator", value=ctx.author.discriminator, inline=False
        )

        embed.add_field(
            name="Roles",
            value=",".join([role.name for role in ctx.author.roles[1:]]),
            inline=False,
        )

        embed.color = self.config.embed_color
        embed.set_thumbnail(url=ctx.author.avatar_url)
        return embed
