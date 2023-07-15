import socket

import base
import discord
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

    irc_cog = DiscordToIRC(bot=bot, models=[IRCChannelMapping], extension_name="relay")

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
        self.bot.irc.send_message_from_discord(ctx.message, result)

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

        if "PRIVMSG" not in message:
            await discord_channel.send(content=message)

        irc_message_split = self.split_irc_message(message)

        discord_channel = await self.bot.fetch_channel(map)

        embed = self.generate_sent_message_embed(
            irc_message_split["username"],
            irc_message_split["content"],
            irc_message_split["channel"],
        )

        await discord_channel.send(embed=embed)

    def split_irc_message(self, irc_message):
        """Splits the raw input from IRC into 4 parts

        Args:
            irc_message (str): The raw IRC message string

        Returns:
            dict: A dictionary containing the username, hostmark, channel, and content
        """
        parts = irc_message.split(" ")

        username = parts[0][1:].split("!")[0]
        hostmask = parts[0].split("@")[1]
        channel = parts[2]
        content = " ".join(parts[3:])[1:]

        return {
            "username": username,
            "hostmask": hostmask,
            "channel": channel,
            "content": content,
        }

    def generate_sent_message_embed(self, author, message, channel):
        """Generates an embed to send to discord stating that a message was sent

        Args:
            author (str): The author of the message
            message (str): The content of the message
            channel (str): The channel in which the message was sent

        Returns:
            discord.Embed: The embed prepared and ready to send
        """
        ICON_URL = "https://cdn.icon-icons.com/icons2/1508/PNG/512/ircchat_104581.png"

        embed = discord.Embed()
        embed.set_author(name=f"{author} - {channel}", icon_url=ICON_URL)
        embed.description = message
        embed.color = discord.Color.blurple()

        return embed
