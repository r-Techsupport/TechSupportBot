import datetime

import base
import discord


def setup(bot):
    config = bot.ExtensionConfig()
    config.add(
        key="channel_map",
        datatype="dict",
        title="Mapping of channel ID's",
        description="Input Channel ID to Logging Channel ID mapping",
        default={},
    )

    bot.add_cog(Logger(bot=bot))
    bot.add_extension_config("logger", config)


class Logger(base.MatchCog):
    async def match(self, config, ctx, _):
        if not str(ctx.channel.id) in config.extensions.logger.channel_map.value:
            return False

        return True

    async def response(self, config, ctx, _, __):
        channel = ctx.guild.get_channel(
            int(config.extensions.logger.channel_map.value.get(str(ctx.channel.id)))
        )
        if not channel:
            return

        await channel.send(embed=self.generate_embed(ctx))

    def generate_embed(self, ctx):
        content = ctx.message.content[:256] if ctx.message.content else "None"

        embed = discord.Embed()
        embed.add_field(name="Content", value=content, inline=False)

        if ctx.message.attachments:
            embed.add_field(
                name="Attachments",
                value=" ".join(
                    attachment.url for attachment in ctx.message.attachments
                ),
            )

        embed.add_field(
            name="Channel",
            value=(f"{ctx.channel.name} ({ctx.channel.mention})") or "Unknown",
        )

        embed.add_field(name="Display Name", value=ctx.author.display_name or "Unknown")

        embed.add_field(name="Name", value=ctx.author.name or "Unknown")

        embed.add_field(name="Discriminator", value=ctx.author.discriminator or "None")

        embed.add_field(
            name="Roles",
            value=(",".join([role.name for role in ctx.author.roles[1:]])) or "None",
            inline=False,
        )

        embed.set_thumbnail(url=ctx.author.avatar_url)
        embed.color = discord.Color.greyple()

        embed.timestamp = datetime.datetime.utcnow()

        return embed
