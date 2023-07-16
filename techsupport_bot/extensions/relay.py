import socket

import base
import discord
from base import auxiliary
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
        # Check if IRC is enabled
        irc_config = getattr(self.bot.file_config.main, "irc")
        if not irc_config.enable_irc:
            return False

        if not self.mapping:
            return False

        # Check if channel has an active map
        if not str(ctx.channel.id) in self.mapping:
            return False

        # If there is a map, find it and return it
        map = self.mapping[str(ctx.channel.id)]
        if map:
            return map

        # If no conditions are met, do nothing
        return False

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
            await auxiliary.send_confirm_embed(
                message=f"Socket {self.bot.irc.irc_socket} appears to be working fine"
            )
        except socket.error as e:
            await ctx.send(content=f"Socket error: {e}")

    @irc.command(name="ban", description="Ban a user on IRC")
    async def irc_ban(self, ctx, *, user: str):
        map = self.mapping[str(ctx.channel.id)]
        if not map:
            await auxiliary.send_deny_embed(
                message="This channel is not linked to IRC", channel=ctx.channel
            )
            return
        if not self.bot.irc.is_bot_op_on_channel(map):
            await auxiliary.send_deny_embed(message=f"The IRC bot does not have permissions to ban", channel=ctx.channel)
            return
        self.bot.irc.ban_on_irc(user=user, channel=map, action="+b")
        await auxiliary.send_confirm_embed(message=f"Sucessfully sent ban command for {user} from {map}", channel=ctx.channel)


    @irc.command(name="unban", description="Unban a user on IRC")
    async def irc_unban(self, ctx, *, user: str):
        map = self.mapping[str(ctx.channel.id)]
        if not map:
            await auxiliary.send_deny_embed(
                message="This channel is not linked to IRC", channel=ctx.channel
            )
            return
        if not self.bot.irc.is_bot_op_on_channel(map):
            await auxiliary.send_deny_embed(message=f"The IRC bot does not have permissions to unban", channel=ctx.channel)
            return
        self.bot.irc.ban_on_irc(user=user, channel=map, action="-b")
        await auxiliary.send_confirm_embed(message=f"Sucessfully sent unban command for {user} from {map}", channel=ctx.channel)

    @irc.command(name="link", description="Add a link")
    async def irc_link(self, ctx, irc_channel: str):
        """Create a new link between discord and IRC

        Args:
            ctx (commands.Context): The context in which the command was run
            irc_channel (str): The string representation of the IRC channel
        """
        if str(ctx.channel.id) in self.mapping:
            await auxiliary.send_deny_embed(
                message=f"This discord channel is already linked to {self.mapping[str(ctx.channel.id)]}",
                channel=ctx.channel,
            )
            return

        if irc_channel in self.mapping.inverse:
            await auxiliary.send_deny_embed(
                message=f"This IRC channel is already linked {self.mapping.inverse[irc_channel]}",
                channel=ctx.channel,
            )
            return

        joined_channels = getattr(self.bot.file_config.main.irc, "channels")

        if not irc_channel in joined_channels:
            await auxiliary.send_deny_embed(
                message="I am not in this IRC channel", channel=ctx.channel
            )
            return

        map = self.models.IRCChannelMapping(
            guild_id=str(ctx.guild.id),
            discord_channel_id=str(ctx.channel.id),
            irc_channel_id=irc_channel,
        )

        self.mapping.put(map.discord_channel_id, map.irc_channel_id)

        await map.create()
        await auxiliary.send_confirm_embed(
            message="New link established", channel=ctx.channel
        )

    async def send_message_from_irc(self, split_message):
        """Sends a message on discord after recieving one on IRC

        Args:
            message (str): The string content of the message
            irc_channel (str): The string representation of the IRC channel
        """
        try:
            map = self.mapping.inverse[split_message["channel"]]
            if not map:
                return

            discord_channel = await self.bot.fetch_channel(map)

            embed = self.generate_sent_message_embed(split_message)

            await discord_channel.send(embed=embed)
        except Exception as e:
            await self.bot.logger.warning(f"{e}")

    def generate_sent_message_embed(self, split_message):
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
        embed.set_author(
            name=f"{split_message['username']} - {split_message['channel']}",
            icon_url=ICON_URL,
        )
        embed.description = split_message["content"]
        embed.set_footer(
            text=f"{split_message['hostmask']} • {getattr(self.bot.file_config.main.irc, 'server')}"
        )
        embed.color = discord.Color.blurple()

        return embed
