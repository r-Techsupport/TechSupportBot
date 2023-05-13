"""Module to set the relay for the discord bot."""
import datetime
import uuid
from multiprocessing.sharedctypes import Value
from xml.dom.minidom import Attr

import base
import discord
import munch
from discord.ext import commands


async def setup(bot):
    """Method to add relay and IRC to the config file."""
    await bot.add_cog(DiscordRelay(bot=bot, no_guild=True, extension_name="relay"))
    await bot.add_cog(IRCReceiver(bot=bot, no_guild=True, extension_name="relay"))


class RelayEvent:
    """Class for the relay event for the discord bot."""

    def __init__(self, type, author, channel):
        self.payload = munch.Munch()
        self.payload.event = munch.Munch()
        self.payload.event.id = str(uuid.uuid4())
        self.payload.event.type = type
        self.payload.event.time = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )

        self.payload.author = munch.Munch()
        self.payload.author.username = author.name
        self.payload.author.id = author.id
        self.payload.author.nickname = author.display_name
        self.payload.author.discriminator = author.discriminator
        self.payload.author.is_bot = author.bot
        self.payload.author.top_role = str(author.top_role)

        self.payload.author.permissions = munch.Munch()
        discord_permissions = channel.permissions_for(author)
        self.payload.author.permissions.kick = discord_permissions.kick_members
        self.payload.author.permissions.ban = discord_permissions.ban_members
        self.payload.author.permissions.unban = discord_permissions.ban_members
        self.payload.author.permissions.admin = discord_permissions.administrator

        self.payload.server = munch.Munch()
        self.payload.server.name = author.guild.name
        self.payload.server.id = author.guild.id

        self.payload.channel = munch.Munch()
        self.payload.channel.name = channel.name
        self.payload.channel.id = channel.id

    def to_json(self):
        """Method to return a json upon payload."""
        return self.payload.toJSON()


class MessageEvent(RelayEvent):
    """Class to send a message event by relay event."""

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        super().__init__("message", *args, **kwargs)

        self.message = message

        self.payload.event.content = message.clean_content
        self.payload.event.attachments = [
            attachment.url for attachment in message.attachments
        ]

        self.payload.event.reply = munch.Munch()

    async def fill_reply_data(self):
        """Method to fill the embed with data from the event."""
        reference = self.message.reference
        if not reference:
            return

        referenced_message = await self.message.channel.fetch_message(
            reference.message_id
        )
        if not referenced_message:
            return

        content = ""
        if referenced_message.clean_content:
            content = referenced_message.clean_content
        elif len(referenced_message.embeds) > 0:
            embed = referenced_message.embeds[0]
            if embed.description:
                content = embed.description
            elif embed.title:
                content = embed.title
            else:
                # reply data is useless
                return

        self.payload.event.reply.content = content

        self.payload.event.reply.author = munch.Munch()
        self.payload.event.reply.author.username = referenced_message.author.name
        self.payload.event.reply.author.id = referenced_message.author.id
        self.payload.event.reply.author.nickname = (
            referenced_message.author.display_name
        )
        self.payload.event.reply.author.discriminator = (
            referenced_message.author.discriminator
        )


class FactoidEvent(RelayEvent):
    """Class to define a factoid event from a relay event."""

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        factoid = kwargs.pop("factoid")
        super().__init__("message", *args, **kwargs)
        self.message = message
        self.payload.event.content = factoid.message
        self.payload.event.attachments = []
        self.payload.event.reply = munch.Munch()


class MessageEditEvent(RelayEvent):
    """Class to edit a message event from a relay event."""

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        super().__init__("message_edit", *args, **kwargs)
        self.payload.event.content = message.clean_content


class ReactionAddEvent(RelayEvent):
    """Method to add a reaction event from a relay event."""

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        emoji = kwargs.pop("emoji")
        super().__init__("reaction_add", *args, **kwargs)
        self.payload.event.emoji = emoji

        content = ""
        if message.clean_content:
            content = message.clean_content
        elif len(message.embeds) > 0:
            embed = message.embeds[0]
            if embed.description:
                content = embed.description
            elif embed.title:
                content = embed.title

        # this might be none still, but kinda rare
        self.payload.event.content = content


class IRCEmbed(discord.Embed):
    """Class for the IRC embed."""

    ICON_URL = "https://cdn.icon-icons.com/icons2/1508/PNG/512/ircchat_104581.png"

    def __init__(self, *args, **kwargs):
        data = kwargs.pop("data")
        super().__init__(*args, **kwargs)
        self.data = data
        self.color = discord.Color.blurple()

    @staticmethod
    def get_permissions_label(permissions):
        """Method to get permission for the label."""
        label = ""
        if permissions:
            if "v" in permissions:
                label += "+"
            if "o" in permissions:
                label += "@"
        return label

    def fill_mentions(self, channel):
        """Method to fill in mentions for the relay message."""
        description = self.description  # pylint: disable=E0203
        if not description:
            raise AttributeError("description field not present")

        new_message = ""
        mention_string = ""
        for word in description.split(" "):
            member = channel.guild.get_member_named(word)
            if member:
                channel_permissions = channel.permissions_for(member)
                if channel_permissions.read_messages:
                    mention = f"{member.mention} "
                    new_message += mention
                    mention_string += mention
                    continue
            new_message += f"{word} "

        self.description = new_message
        return mention_string


class IRCMessageEmbed(IRCEmbed):
    """Class for IRC embedded messages."""

    ICON_URL = "https://cdn.icon-icons.com/icons2/1508/PNG/512/ircchat_104581.png"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_author(
            name=f"{self.get_permissions_label(self.data.author.permissions)}\
                {self.data.author.nickname} - {self.data.server.name}/{self.data.channel.name}",
            icon_url=self.ICON_URL,
        )
        self.description = self.data.event.content


class IRCEventEmbed(IRCEmbed):
    """Class for IRC event embeds."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_author(
            name=f"IRC Event - {self.data.server.name}/{self.data.channel.name}",
            icon_url=self.ICON_URL,
        )
        self.description = self.generate_event_message()

    def generate_event_message(self):  # Maybe edit to a switch statement.
        """Method to generate the event message from IRC."""
        permissions_label = self.get_permissions_label(self.data.author.permissions)
        if self.data.event.type == "join":
            return f"`{permissions_label}{self.data.author.mask}` \
                has joined {self.data.channel.name}!"
        if self.data.event.type == "part":
            return f"`{permissions_label}{self.data.author.mask}` \
                left {self.data.channel.name}!"
        if self.data.event.type == "quit":
            return f"`{permissions_label}{self.data.author.mask}` \
                quit ({self.data.event.content})"
        if self.data.event.type == "kick":
            return f"`{permissions_label}{self.data.author.mask}` kicked \
                `{self.data.event.target}` from {self.data.channel.name}! \
                (reason: *{self.data.event.content}*)."
        if self.data.event.type == "action":
            return f"`{permissions_label}{self.data.author.nickname}` {self.data.event.content}"
        if self.data.event.type == "other":
            if self.data.event.irc_command.lower() == "mode":
                return f"`{permissions_label}{self.data.author.nickname}` \
                    sets mode **{self.data.event.irc_paramlist[1]}** on \
                    `{self.data.event.irc_paramlist[2]}`"
            else:  # Pylint doesn't like this else R1705
                return f"`{self.data.author.mask}` did some \
                    configuration on {self.data.channel.name}..."
        # Needs a return for the function itself
        # maybe? (return f"`{self.data.author.nickname}` could not send message.")


class DiscordRelay(base.MatchCog):
    """Class for discord relay."""

    async def preconfig(self):
        """Method to preconfig the discord relay."""
        self.listen_channels = list(
            self.bot.file_config.special.relay.channel_map.values()
        )

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        """Method to edit the raw message on the relay."""
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        if not channel.id in self.listen_channels:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message or message.author.bot:
            return

        # removes embed-generation events
        old_content = getattr(payload.cached_message, "content", None)
        if old_content == message.content:
            return

        edit_event = MessageEditEvent(message.author, channel, message=message)

        await self.publish(edit_event.to_json(), message.guild)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Method to add a raw reaction on a relay."""
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        if not channel.id in self.listen_channels:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message or message.author.bot:
            return

        emoji = (
            payload.emoji.name
            if payload.emoji.is_unicode_emoji()
            else f":{payload.emoji.name}:"
        )
        reaction_add_event = ReactionAddEvent(
            payload.member,
            channel,
            message=message,
            emoji=emoji,
        )

        await self.publish(reaction_add_event.to_json(), message.guild)

    async def match(self, _, ctx, content):
        """Method to match channel for the relay."""
        if not ctx.channel.id in self.listen_channels:
            return False
        return True

    async def response(self, _, ctx, __, ___):
        """Method to create the response for the relay message."""
        message_event = MessageEvent(
            ctx.author,
            ctx.channel,
            message=ctx.message,
        )
        await message_event.fill_reply_data()
        await self.publish(message_event.to_json(), ctx.message.guild)

    async def publish(self, payload, guild):
        """Method to publish the relay message."""
        try:
            await self.bot.rabbit_publish(
                payload, self.bot.file_config.special.relay.send_queue
            )
        except Exception as e:
            await self.bot.guild_log(
                guild,
                "logging_channel",
                "error",
                "Could not publish Discord event to relay broker",
                send=True,
                exception=e,
            )

    @commands.Cog.listener()
    async def on_factoid_event(self, payload):
        """Method to allow a factoid event from a payload."""
        message_event = FactoidEvent(
            payload.author,
            payload.message.channel,
            message=payload.message,
            factoid=payload.factoid,
        )
        await self.publish(message_event.to_json(), payload.message.channel.guild)


class IRCReceiver(base.LoopCog):
    """Class to recieve the IRC event."""

    IRC_LOGO = "📨"
    # start the receiver right away
    ON_START = True

    async def loop_preconfig(self):
        """Method to preconfig the loop for the relay."""
        self.listen_channels = list(
            self.bot.file_config.special.relay.channel_map.values()
        )

    async def execute(self, _config, guild):
        """Method to execute and send a message from IRC."""
        try:
            await self.bot.rabbit_consume(
                self.bot.file_config.special.relay.recv_queue,
                self.handle_event,
                poll_wait=1,
                durable=True,
            )
        except Exception as e:
            await self.bot.guild_log(
                guild,
                "logging_channel",
                "error",
                f"Could not consume IRC event from relay broker \
                    (will restart consuming in {self.DEFAULT_WAIT} seconds)",
                send=True,
                exception=e,
            )

    async def handle_event(self, response):
        """Method to handle an event from IRC."""
        data = self.deserialize(response)
        if not data:
            return

        if not data.event.type in ["message", "join", "part", "quit", "kick", "action"]:
            return

        embed = self.process_embed(data)

        if data.event.type == "quit":
            for channel_id in self.listen_channels:
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    continue
                await channel.send(embed=embed)
            return

        channel = self.get_channel(data)
        if not channel:
            return

        mentions = embed.fill_mentions(channel)
        await channel.send(content=mentions, embed=embed)

        self.bot.dispatch(
            "extension_listener_event", munch.Munch(channel=channel, embed=embed)
        )

    @staticmethod
    def _add_mentions(message, guild, channel):
        """Method to add mentions to the IRC message."""
        new_message = ""
        for word in message.split(" "):
            member = guild.get_member_named(word)
            if member:
                channel_permissions = channel.permissions_for(member)
                if channel_permissions.read_messages:
                    new_message += f"{member.mention} "
                    continue
            new_message += f"{word} "
        return new_message

    def get_channel(self, data):
        """Method to get the channel for the IRC event."""
        for channel_id in self.listen_channels:
            if channel_id == self.bot.file_config.special.relay.channel_map.get(
                data.channel.name
            ):
                return self.bot.get_channel(int(channel_id))
        # Need a return statement for the function itself

    def deserialize(self, body):
        """Method to deserialize the time of the event."""
        deserialized = munch.Munch.fromJSON(body)

        time = deserialized.event.time
        if not time:
            return
        if self.time_stale(time):
            return

        return deserialized
        # R1710 all need to return an expression

    def time_stale(self, time):
        """Method to format the time for the event."""
        time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        if (
            now - time
        ).total_seconds() > self.bot.file_config.special.relay.stale_seconds:
            return True

        return False

    def process_embed(self, data):
        """Method to process the embed of the event."""
        if data.event.type == "message":
            return IRCMessageEmbed(data=data)
        return IRCEventEmbed(data=data)
