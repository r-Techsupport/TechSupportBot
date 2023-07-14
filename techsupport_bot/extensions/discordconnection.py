import socket

import base
from discord.ext import commands


async def setup(bot):
    """Method to add the directory to the config."""

    class IRCChannelMapping(bot.db.Model):
        """Class to add the directory to the config."""

        __tablename__ = "ircchannelmap"
        map_id = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id = bot.db.Column(bot.db.String, default=None)
        discord_channel_id = bot.db.Column(bot.db.String, default=None)
        irc_channel_id = bot.db.Column(bot.db.String, default=None)

    await bot.add_cog(
        DiscordToIRC(
            bot=bot, models=[IRCChannelMapping], extension_name="discordconnection"
        )
    )


class DiscordToIRC(base.MatchCog):
    async def match(self, config, ctx, content):
        """Method to match the logging channel to the map."""
        map = (
            await self.models.IRCChannelMapping.query.where(
                self.models.IRCChannelMapping.discord_channel_id == str(ctx.channel.id)
            )
            .where(self.models.IRCChannelMapping.guild_id == str(ctx.guild.id))
            .gino.first()
        )
        if map:
            return map.irc_channel_id

    async def response(self, config, ctx, content, result):
        """Method to generate the response from the logger."""
        self.bot.irc.send_message_from_discord(content, result)

    @commands.group(
        brief="Executes an irc command",
        description="Executes an irc command",
    )
    async def irc(self, ctx):
        await base.extension_help(self, ctx, self.__module__[11:])

    @irc.command(name="maps", description="List all the maps for IRC")
    async def irc_maps(self, ctx):
        allmaps = await self.models.IRCChannelMapping.query.gino.all()

        await ctx.send(content=f"maps: {allmaps}")

    @irc.command(name="socket", description="Print socket")
    async def irc_socket(self, ctx):
        await ctx.send(content=f"{self.bot.irc.irc_socket}")

    @irc.command(name="status", description="Check status")
    async def irc_status(self, ctx):
        try:
            self.bot.irc.irc_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            await ctx.send(content="Socket is active and working.")
        except socket.error as e:
            await ctx.send(content=f"Socket error: {e}")

    @irc.command(name="link", description="Add a link")
    async def irc_link(self, ctx, irc_channel: str):
        map = self.models.IRCChannelMapping(
            guild_id=str(ctx.guild.id),
            discord_channel_id=str(ctx.channel.id),
            irc_channel_id=irc_channel,
        )

        await map.create()
