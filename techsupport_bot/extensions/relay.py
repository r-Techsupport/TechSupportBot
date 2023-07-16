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

    @irc.command(name="status", description="Check status")
    async def irc_status(self, ctx):
        """Determines if the IRC socket is connected or not

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        status = self.bot.irc.get_irc_status()
        await ctx.send(content=status)

    @commands.has_permissions(ban_members=True)
    @irc.command(name="ban", description="Ban a user on IRC")
    async def irc_ban(self, ctx, *, user: str):
        map = self.mapping[str(ctx.channel.id)]
        if not map:
            await auxiliary.send_deny_embed(
                message="This channel is not linked to IRC", channel=ctx.channel
            )
            return
        if not self.bot.irc.is_bot_op_on_channel(map):
            await auxiliary.send_deny_embed(
                message=f"The IRC bot does not have permissions to ban",
                channel=ctx.channel,
            )
            return
        self.bot.irc.ban_on_irc(user=user, channel=map, action="+b")
        await auxiliary.send_confirm_embed(
            message=f"Sucessfully sent ban command for {user} from {map}",
            channel=ctx.channel,
        )

    @commands.has_permissions(ban_members=True)
    @irc.command(name="unban", description="Unban a user on IRC")
    async def irc_unban(self, ctx, *, user: str):
        map = self.mapping[str(ctx.channel.id)]
        if not map:
            await auxiliary.send_deny_embed(
                message="This channel is not linked to IRC", channel=ctx.channel
            )
            return
        if not self.bot.irc.is_bot_op_on_channel(map):
            await auxiliary.send_deny_embed(
                message=f"The IRC bot does not have permissions to unban",
                channel=ctx.channel,
            )
            return
        self.bot.irc.ban_on_irc(user=user, channel=map, action="-b")
        await auxiliary.send_confirm_embed(
            message=f"Sucessfully sent unban command for {user} from {map}",
            channel=ctx.channel,
        )

    @commands.has_permissions(administrator=True)
    @irc.command(name="link", description="Add a link between IRC and discord")
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
                message=f"This IRC channel is already linked <#{self.mapping.inverse[irc_channel]}>",
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
            message=f"New link established between <#{ctx.channel.id}> and {irc_channel}",
            channel=ctx.channel,
        )

    @commands.has_permissions(administrator=True)
    @irc.command(name="unlink", description="Remove a link between IRC and discord")
    async def irc_unlink(self, ctx):
        if str(ctx.channel.id) not in self.mapping:
            await auxiliary.send_deny_embed(
                message="This discord channel is not linked to any IRC channel",
                channel=ctx.channel,
            )
            return

        irc_channel = self.mapping.pop(str(ctx.channel.id))

        db_link = await self.models.IRCChannelMapping.query.where(
            self.models.IRCChannelMapping.discord_channel_id == str(ctx.channel.id)
        ).gino.first()

        print(db_link)

        await db_link.delete()

        await auxiliary.send_confirm_embed(
            message=f"Successfully deleted link between <#{ctx.channel.id}> and {irc_channel}",
            channel=ctx.channel,
        )

    async def send_message_from_irc(self, split_message):
        """Sends a message on discord after recieving one on IRC

        Args:
            message (str): The string content of the message
            irc_channel (str): The string representation of the IRC channel
        """
        try:
            if split_message["channel"] not in self.mapping.inverse:
                return

            map = self.mapping.inverse[split_message["channel"]]

            discord_channel = await self.bot.fetch_channel(map)

            mentions = self.get_mentions(
                message=split_message["content"], channel=discord_channel
            )
            mentions_string = auxiliary.construct_mention_string(mentions)

            embed = self.generate_sent_message_embed(split_message)

            await discord_channel.send(content=mentions_string, embed=embed)
        except Exception as e:
            await self.bot.logger.warning(f"{e}")

    def get_mentions(self, message, channel):
        mentions = []
        for word in message.split(" "):
            member = channel.guild.get_member_named(word)
            if member:
                channel_permissions = channel.permissions_for(member)
                if channel_permissions.read_messages:
                    mentions.append(member)
                    continue
        return mentions

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

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        channel = before.channel
        if not channel:
            return

        if str(channel.id) not in self.mapping:
            return

        if before.author.bot:
            return

        # removes embed-generation events
        if before.clean_content == after.clean_content:
            return

        self.bot.irc.send_edit_from_discord(after, self.mapping[str(channel.id)])

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        channel = reaction.message.channel

        if str(channel.id) not in self.mapping:
            return

        if len(reaction.message.content.strip()) == 0:
            return

        self.bot.irc.send_reaction_from_discord(
            reaction, user, self.mapping[str(channel.id)]
        )
