import asyncio
import socket

import base
from bidict import bidict
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

    irc_cog = DiscordToIRC(
        bot=bot, models=[IRCChannelMapping], extension_name="discordconnection"
    )

    await bot.add_cog(irc_cog)
    bot.irc.irc_cog = irc_cog


class DiscordToIRC(base.MatchCog):
    mapping = None  # bidict - discord:irc

    async def preconfig(self):
        allmaps = await self.models.IRCChannelMapping.query.gino.all()
        self.mapping = bidict({})
        for map in allmaps:
            self.mapping.put(map.discord_channel_id, map.irc_channel_id)

    async def match(self, config, ctx, content):
        """Method to match the logging channel to the map."""
        if not str(ctx.channel.id) in self.mapping:
            return False
        map = self.mapping[str(ctx.channel.id)]
        if map:
            return map

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
        # allmaps = await self.models.IRCChannelMapping.query.gino.all()

        await ctx.send(content=f"maps: {self.mapping}")

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

        self.mapping.put(map.discord_channel_id, map.irc_channel_id)

        await map.create()

    async def send_message_from_irc(self, message, irc_channel):
        map = self.mapping.inverse[irc_channel]
        if not map:
            return

        discord_channel = await self.bot.fetch_channel(map)
        await discord_channel.send(content=f"{message}")
