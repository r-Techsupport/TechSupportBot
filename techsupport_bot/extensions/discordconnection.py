import datetime
import io
import json

import base
import discord
import util
from base import auxiliary
from discord.ext import commands
import socket

async def setup(bot):
    """Method to add the directory to the config."""

    class IRCChannelMapping(bot.db.Model):
        """Class to add the directory to the config."""

        __tablename__ = "ircchannelmaps"
        guild_id = bot.db.Column(bot.db.String, primary_key=True)
        discord_channel_id = bot.db.Column(bot.db.String, default=None)
        irc_channel_id = bot.db.Column(bot.db.String, default=None)


    await bot.add_cog(DiscordToIRC(bot=bot, models=[IRCChannelMapping]))


class DiscordToIRC(base.BaseCog):

    @commands.group(
        brief="Executes an irc command",
        description="Executes an irc command",
    )
    async def irc(self, ctx):
        """Makes the .grab command group"""
        # Executed if there are no/invalid args supplied
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
            await ctx.send(content='Socket is active and working.')
        except socket.error as e:
            await ctx.send(content=f'Socket error: {e}')