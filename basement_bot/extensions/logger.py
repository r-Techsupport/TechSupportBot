import datetime

import base
import discord
from discord.ext import commands


def setup(bot):
    config = bot.ExtensionConfig()
    config.add(
        key="channel_map",
        datatype="dict",
        title="Mapping of channel ID's",
        description="Input Channel ID to Logging Channel ID mapping",
        default={},
    )

    bot.add_cog(Logger(bot=bot, extension_name="logger"))
    bot.add_extension_config("logger", config)


class LogEmbed(discord.Embed):
    def __init__(self, *args, **kwargs):
        ctx = kwargs.pop("context")
        super().__init__(*args, **kwargs)

        content = ctx.message.content[:256] if ctx.message.content else "None"

        self.add_field(name="Content", value=content, inline=False)

        if ctx.message.attachments:
            self.add_field(
                name="Attachments",
                value=" ".join(
                    attachment.url for attachment in ctx.message.attachments
                ),
            )

        self.add_field(
            name="Channel",
            value=(f"{ctx.channel.name} ({ctx.channel.mention})") or "Unknown",
        )
        self.add_field(name="Display Name", value=ctx.author.display_name or "Unknown")
        self.add_field(name="Name", value=ctx.author.name or "Unknown")
        self.add_field(name="Discriminator", value=ctx.author.discriminator or "None")
        self.add_field(
            name="Roles",
            value=(",".join([role.name for role in ctx.author.roles[1:]])) or "None",
            inline=False,
        )

        self.set_thumbnail(url=ctx.author.avatar_url)
        self.color = discord.Color.greyple()

        self.timestamp = datetime.datetime.utcnow()


class Logger(base.MatchCog):
    async def match(self, config, ctx, _):
        if not str(ctx.channel.id) in config.extensions.logger.channel_map.value:
            return False

        return True

    async def response(self, config, ctx, _, __):
        channel = ctx.guild.get_channel(
            int(config.extensions.logger.channel_map.value.get(ctx.channel.id))
        )
        if not channel:
            return

        if channel.guild.id != ctx.guild.id:
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "warning",
                "Configured channel not in associated guild - aborting log",
                send=True,
            )
            return

        await channel.send(embed=LogEmbed(context=ctx))
