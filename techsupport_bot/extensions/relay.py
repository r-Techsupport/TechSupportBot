import socket

import base
from bidict import bidict
from discord.ext import commands


async def setup(bot):
    """Setup function for the IRC relay
    This is sets up the IRC postgres table, adds the irc cog,
        and adds a refernce to it to the irc file

    Args:
        bot (commands.Bot): The bot object
    """

    class IRCChannelMapping(bot.db.Model):
        """The database table for the IRC channel maps

        Args:
            bot (commands.Bot): The bot object
        """

        __tablename__ = "ircchannelmap"
        map_id = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id = bot.db.Column(bot.db.String, default=None)
        discord_channel_id = bot.db.Column(bot.db.String, default=None)
        irc_channel_id = bot.db.Column(bot.db.String, default=None)

    irc_cog = DiscordToIRC(
        bot=bot, models=[IRCChannelMapping], extension_name="relay"
    )

    await bot.add_cog(irc_cog)
    bot.irc.irc_cog = irc_cog


class DiscordToIRC(base.MatchCog):
    """The discord side of the relay"""

    mapping = None  # bidict - discord:irc

    async def preconfig(self):
        """The preconfig setup for the discord side
        This maps the database to a bidict for quick lookups, and allows lookups in threads
        """
        allmaps = await self.models.IRCChannelMapping.query.gino.all()
        self.mapping = bidict({})
        for map in allmaps:
            self.mapping.put(map.discord_channel_id, map.irc_channel_id)

    async def match(self, config, ctx, content):
        """Checks to see if the message should be sent to discord

        Args:
            config (_type_): The config of the guild where the message was sent
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message

        Returns:
            str: The string representation of the IRC channel. Will be False if no IRC mapping
        """
        if not str(ctx.channel.id) in self.mapping:
            return False
        map = self.mapping[str(ctx.channel.id)]
        if map:
            return map

    async def response(self, config, ctx, content, result):
        """Send the message to IRC

        Args:
            config (_type_): The config of the guild where the message was sent
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message
            result (str): The string representation of the IRC channel
        """
        self.bot.irc.send_message_from_discord(content, result)

    @commands.group(
        brief="Executes an irc command",
        description="Executes an irc command",
    )
    async def irc(self, ctx):
        """The base set of IRC commands

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        await base.extension_help(self, ctx, self.__module__[11:])

    @irc.command(name="maps", description="List all the maps for IRC")
    async def irc_maps(self, ctx):
        """Show the current IRC maps

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        # allmaps = await self.models.IRCChannelMapping.query.gino.all()

        await ctx.send(content=f"maps: {self.mapping}")

    @irc.command(name="socket", description="Print socket")
    async def irc_socket(self, ctx):
        """Prints the IRC socket

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        await ctx.send(content=f"{self.bot.irc.irc_socket}")

    @irc.command(name="status", description="Check status")
    async def irc_status(self, ctx):
        """Determines if the IRC socket is connected or not

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        try:
            self.bot.irc.irc_socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            await ctx.send(content="Socket is active and working.")
        except socket.error as e:
            await ctx.send(content=f"Socket error: {e}")

    @irc.command(name="link", description="Add a link")
    async def irc_link(self, ctx, irc_channel: str):
        """Create a new link between discord and IRC

        Args:
            ctx (commands.Context): The context in which the command was run
            irc_channel (str): The string representation of the IRC channel
        """
        map = self.models.IRCChannelMapping(
            guild_id=str(ctx.guild.id),
            discord_channel_id=str(ctx.channel.id),
            irc_channel_id=irc_channel,
        )

        self.mapping.put(map.discord_channel_id, map.irc_channel_id)

        await map.create()

    async def send_message_from_irc(self, message, irc_channel):
        """Sends a message on discord after recieving one on IRC

        Args:
            message (str): The string content of the message
            irc_channel (str): The string representation of the IRC channel
        """
        map = self.mapping.inverse[irc_channel]
        if not map:
            return

        discord_channel = await self.bot.fetch_channel(map)
        await discord_channel.send(content=f"{message}")
