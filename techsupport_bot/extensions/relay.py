"""This is the discord side of the IRC->Discord relay"""
from typing import Dict, List, Union

import base
import discord
import munch
import ui
from base import auxiliary
from bidict import bidict
from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
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

    async def match(
        self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> str:
        """Checks to see if the message should be sent to discord

        Args:
            config (munch.Munch): The config of the guild where the message was sent
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message

        Returns:
            str: The string representation of the IRC channel. Will be None if no IRC mapping
        """
        # Check if IRC is enabled
        irc_config = getattr(self.bot.file_config.main, "irc")
        if not irc_config.enable_irc:
            return None

        if not self.mapping:
            return None

        # Check if channel has an active map
        if not str(ctx.channel.id) in self.mapping:
            return None

        # If there is a map, find it and return it
        map = self.mapping[str(ctx.channel.id)]
        if map:
            return map

        # If no conditions are met, do nothing
        return None

    async def response(
        self, config: munch.Munch, ctx: commands.Context, content: str, result: str
    ) -> None:
        """Send the message to IRC

        Args:
            config (munch.Munch): The config of the guild where the message was sent
            ctx (commands.Context): The context the message was sent in
            content (str): The string content of the message
            result (str): The string representation of the IRC channel
        """
        if self.bot.irc.ready:
            self.bot.irc.send_message_from_discord(message=ctx.message, channel=result)

    async def handle_factoid(
        self,
        channel: discord.abc.Messageable,
        discord_message: discord.Message,
        factoid_message: str,
    ) -> None:
        """A method to handle a factoid event and send a message to IRC with the content of
        the factoid but the author of the factoid invoker

        Args:
            channel (discord.abc.Messageable): The discord channel the factoid was called in
            discord_message (discord.Message): The original containing the invocation of the factoid
            factoid_message (str): The string representation of the factoid
        """
        irc_config = getattr(self.bot.file_config.main, "irc")
        if not irc_config.enable_irc:
            return

        if not self.mapping:
            return

        # Check if channel has an active map
        if not str(channel.id) in self.mapping:
            return

        self.bot.irc.send_message_from_discord(
            message=discord_message,
            channel=self.mapping[str(channel.id)],
            content_override=factoid_message,
        )

    @commands.group(
        brief="Executes an irc command",
        description="Executes an irc command",
    )
    async def irc(self, ctx: commands.Context) -> None:
        """The base set of IRC commands

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        await base.extension_help(self, ctx, self.__module__[11:])

    @irc.command(name="maps", description="List all the maps for IRC")
    async def irc_maps(self, ctx: commands.Context) -> None:
        """Show the current IRC maps

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        db_links = await self.models.IRCChannelMapping.query.where(
            self.models.IRCChannelMapping.guild_id == str(ctx.guild.id)
        ).gino.all()

        embed = discord.Embed()
        embed.title = "All IRC links:"
        embed.color = discord.Color.blurple()

        for entry in db_links:
            embed.add_field(
                name=f"<#{entry.discord_channel_id}>",
                value=entry.irc_channel_id,
                inline=True,
            )

        await ctx.send(embed=embed)

    @commands.has_permissions(administrator=True)
    @irc.command(name="disconnect", description="Disconnect from IRC")
    async def irc_disconnect(self, ctx: commands.Context) -> None:
        """Disconnects from IRC

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        if not self.bot.irc.connection.is_connected():
            await auxiliary.send_deny_embed(
                message="IRC is not connected", channel=ctx.channel
            )
        self.bot.irc.ready = False
        self.bot.irc.connection.disconnect()
        await auxiliary.send_confirm_embed(
            message="Disconnected from IRC", channel=ctx.channel
        )

    @commands.has_permissions(administrator=True)
    @irc.command(name="reconnect", description="Reconnects to IRC")
    async def irc_reconnect(self, ctx: commands.Context) -> None:
        """Reconnects to IRC

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        self.bot.irc.ready = False
        self.bot.irc.connection.reconnect()
        await auxiliary.send_confirm_embed(
            message="Reconnected to IRC", channel=ctx.channel
        )

    @irc.command(name="status", description="Check status")
    async def irc_status(self, ctx: commands.Context) -> None:
        """Prints some basic status of the IRC bot
        This same info is available in .bot

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        embed = auxiliary.generate_basic_embed(
            title="IRC status",
            description="",
            color=discord.Color.blurple(),
        )

        irc_status = self.bot.irc.get_irc_status()
        irc_config = getattr(self.bot.file_config.main, "irc")
        if not irc_config.enable_irc:
            embed.description = "IRC is not enabled"
        embed.description = (
            f"IRC Status: `{irc_status['status']}` \n"
            f"IRC Bot Name: `{irc_status['name']}` \n"
            f"Channels: `{irc_status['channels']}`"
        )
        await ctx.send(embed=embed)

    @commands.has_permissions(ban_members=True)
    @irc.command(name="ban", description="Ban a user on IRC")
    async def irc_ban(self, ctx: commands.Context, *, user: str) -> None:
        """A discord command to ban someone on the linked IRC channel

        Args:
            ctx (commands.Context): The context in which the command was run
            user (str): The hostmask of the user to ban
        """
        map = self.mapping[str(ctx.channel.id)]
        if not map:
            await auxiliary.send_deny_embed(
                message="This channel is not linked to IRC", channel=ctx.channel
            )
            return
        if not self.bot.irc.is_bot_op_on_channel(channel_name=map):
            await auxiliary.send_deny_embed(
                message="The IRC bot does not have permissions to ban",
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
    async def irc_unban(self, ctx: commands.Context, *, user: str) -> None:
        """A discord command to unban someone on the linked IRC channel

        Args:
            ctx (commands.Context): The context in which the command was run
            user (str): The hostmask of the user to ban
        """
        map = self.mapping[str(ctx.channel.id)]
        if not map:
            await auxiliary.send_deny_embed(
                message="This channel is not linked to IRC", channel=ctx.channel
            )
            return
        if not self.bot.irc.is_bot_op_on_channel(channel_name=map):
            await auxiliary.send_deny_embed(
                message="The IRC bot does not have permissions to unban",
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
    async def irc_link(self, ctx: commands.Context, irc_channel: str) -> None:
        """Create a new link between discord and IRC

        Args:
            ctx (commands.Context): The context in which the command was run
            irc_channel (str): The string representation of the IRC channel
        """
        if str(ctx.channel.id) in self.mapping:
            await auxiliary.send_deny_embed(
                message="This discord channel is already linked "
                + f"to {self.mapping[str(ctx.channel.id)]}",
                channel=ctx.channel,
            )
            return

        if irc_channel in self.mapping.inverse:
            await auxiliary.send_deny_embed(
                message="This IRC channel is already linked"
                + f"to <#{self.mapping.inverse[irc_channel]}>",
                channel=ctx.channel,
            )
            return

        joined_channels = getattr(self.bot.file_config.main.irc, "channels")

        if not irc_channel in joined_channels:
            await auxiliary.send_deny_embed(
                message="I am not in that IRC channel", channel=ctx.channel
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
            message=(
                f"New link established between <#{ctx.channel.id}> and {irc_channel}"
            ),
            channel=ctx.channel,
        )

    @commands.has_permissions(administrator=True)
    @irc.command(name="unlink", description="Remove a link between IRC and discord")
    async def irc_unlink(self, ctx: commands.Context) -> None:
        """Deletes the link in the current discord channel

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        if str(ctx.channel.id) not in self.mapping:
            await auxiliary.send_deny_embed(
                message="This discord channel is not linked to any IRC channel",
                channel=ctx.channel,
            )
            return

        view = ui.Confirm()
        await view.send(
            message=f"Are you sure you want to unlink <#{ctx.channel.id}>"
            + f"and {self.mapping[str(ctx.channel.id)]}",
            channel=ctx.channel,
            author=ctx.author,
        )
        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return
        if view.value is ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                message=f"The link between <#{ctx.channel.id}> "
                + f"and {self.mapping[str(ctx.channel.id)]} was not deleted",
                channel=ctx.channel,
            )
            return

        irc_channel = self.mapping.pop(str(ctx.channel.id))

        db_link = await self.models.IRCChannelMapping.query.where(
            self.models.IRCChannelMapping.discord_channel_id == str(ctx.channel.id)
        ).gino.first()

        await db_link.delete()

        await auxiliary.send_confirm_embed(
            message=(
                f"Successfully deleted link between <#{ctx.channel.id}> and"
                f" {irc_channel}"
            ),
            channel=ctx.channel,
        )

    async def send_message_from_irc(self, split_message: Dict[str, str]) -> None:
        """Sends a message on discord after recieving one on IRC

        Args:
            split_message (Dict[str, str]): The formatted dictionary of the IRC message
        """
        if split_message["channel"] not in self.mapping.inverse:
            return

        map = self.mapping.inverse[split_message["channel"]]

        discord_channel = await self.bot.fetch_channel(map)

        mentions = self.get_mentions(
            message=split_message["content"], channel=discord_channel
        )
        mentions_string = auxiliary.construct_mention_string(targets=mentions)

        embed = self.generate_sent_message_embed(split_message=split_message)

        await discord_channel.send(content=mentions_string, embed=embed)

    def get_mentions(
        self, message: str, channel: discord.abc.Messageable
    ) -> List[discord.Member]:
        """A function to turn plain text into mentioned from IRC

        Args:
            message (str): The string message from IRC
            channel (discord.abc.Messageable): The channel that the IRC message will be sent to

        Returns:
            List[discord.Member]: The potentially duplicated list members found from the message
        """
        mentions = []
        for word in message.split(" "):
            member = channel.guild.get_member_named(word)
            if member:
                channel_permissions = channel.permissions_for(member)
                if channel_permissions.read_messages:
                    mentions.append(member)
                    continue
        return mentions

    def generate_sent_message_embed(
        self, split_message: Dict[str, str]
    ) -> discord.Embed:
        """Generates an embed to send to discord stating that a message was sent

        Args:
            split_message (Dict[str, str]): The formatted dictionary of the IRC message

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
            text=(
                f"{split_message['hostmask']} •"
                f" {getattr(self.bot.file_config.main.irc, 'server')}"
            )
        )
        embed.color = discord.Color.blurple()

        return embed

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        """Automatically called on every message edit on discord
        If the edit occured in a linked channel, a message is sent to IRC

        Args:
            before (discord.Message): The message object prior to editing
            after (discord.Message): The message object after the edit
        """
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

        self.bot.irc.send_edit_from_discord(
            message=after, channel=self.mapping[str(channel.id)]
        )

    @commands.Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: Union[discord.User, discord.Member]
    ) -> None:
        """Automatically called on every reaction added on discord
        If the reaction was added to a message in a linked channel, a message is sent to IRC

        Args:
            reaction (discord.Reaction): The reaction added to the message
            user (Union[discord.User, discord.Member]): The member who added the reaction
        """
        channel = reaction.message.channel

        if str(channel.id) not in self.mapping:
            return

        if len(reaction.message.content.strip()) == 0:
            return

        self.bot.irc.send_reaction_from_discord(
            reaction=reaction, user=user, channel=self.mapping[str(channel.id)]
        )

    async def handle_dm_from_irc(self, message: str, event) -> None:
        """Sends a DM to the owner of the bot based on a message from IRC

        Args:
            message (str): The message from IRC that the IRC Bot recieved
            event (irc.client.Event): The event object that triggered this function
        """
        owner = await self.bot.get_owner()
        await owner.send(f"PM from `{event.source}`: {message}")
