import datetime
import uuid

import base
import discord
import munch
from discord.ext import commands


def setup(bot):
    bot.add_cog(DiscordRelay(bot=bot, no_guild=True, extension_name="relay"))
    bot.add_cog(IRCReceiver(bot=bot, no_guild=True, extension_name="relay"))


class RelayEvent:
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
        discord_permissions = author.permissions_in(channel)
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
        return self.payload.toJSON()


class MessageEvent(RelayEvent):
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
        reference = self.message.reference
        if not reference:
            return

        referenced_message = await self.message.channel.fetch_message(
            reference.message_id
        )
        if not referenced_message:
            return

        self.payload.event.reply.content = referenced_message.clean_content

        self.payload.event.reply.author = munch.Munch()
        self.payload.event.reply.author.username = referenced_message.author.name
        self.payload.event.reply.author.id = referenced_message.author.id
        self.payload.event.reply.author.nickname = (
            referenced_message.author.display_name
        )
        self.payload.event.reply.author.discriminator = (
            referenced_message.author.discriminator
        )


class MessageEditEvent(RelayEvent):
    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        super().__init__("message_edit", *args, **kwargs)
        self.payload.event.content = message.clean_content


class ReactionAddEvent(RelayEvent):
    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        emoji = kwargs.pop("emoji")
        super().__init__("reaction_add", *args, **kwargs)
        self.payload.event.emoji = emoji
        self.payload.event.content = message.clean_content


class IRCEmbed(discord.Embed):

    ICON_URL = "https://cdn.icon-icons.com/icons2/1508/PNG/512/ircchat_104581.png"

    def __init__(self, *args, **kwargs):
        data = kwargs.pop("data")
        super().__init__(*args, **kwargs)
        self.data = data
        self.color = discord.Color.blurple()
        self.set_footer(text=f"IRC {self.data.server.name} - {self.data.channel.name}")

    @staticmethod
    def get_permissions_label(permissions):
        label = ""
        if permissions:
            if "v" in permissions:
                label += "+"
            if "o" in permissions:
                label += "@"
        return label


class IRCMessageEmbed(IRCEmbed):

    ICON_URL = "https://cdn.icon-icons.com/icons2/1508/PNG/512/ircchat_104581.png"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_author(
            name=f"{self.get_permissions_label(self.data.author.permissions)}{self.data.author.nickname}",
            icon_url=self.ICON_URL,
        )
        self.description = self.data.event.content


class IRCEventEmbed(IRCEmbed):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_author(name="IRC Event", icon_url=self.ICON_URL)
        self.description = self.generate_event_message()

    def generate_event_message(self):
        permissions_label = self.get_permissions_label(self.data.author.permissions)
        if self.data.event.type == "join":
            return f"`{permissions_label}{self.data.author.mask}` has joined {self.data.channel.name}!"
        elif self.data.event.type == "part":
            return f"`{permissions_label}{self.data.author.mask}` left {self.data.channel.name}!"
        elif self.data.event.type == "quit":
            return f"`{permissions_label}{self.data.author.mask}` quit ({self.data.event.content})"
        elif self.data.event.type == "kick":
            return f"`{permissions_label}{self.data.author.mask}` kicked `{self.data.event.target}` from {self.data.channel.name}! (reason: *{self.data.event.content}*)."
        elif self.data.event.type == "action":
            return f"`{permissions_label}{self.data.author.nickname}` {self.data.event.content}"
        elif self.data.event.type == "other":
            if self.data.event.irc_command.lower() == "mode":
                return f"`{permissions_label}{self.data.author.nickname}` sets mode **{self.data.event.irc_paramlist[1]}** on `{self.data.event.irc_paramlist[2]}`"
            else:
                return f"`{self.data.author.mask}` did some configuration on {self.data.channel.name}..."


class DiscordRelay(base.MatchCog):
    async def preconfig(self):
        self.listen_channels = list(
            self.bot.file_config.special.relay.channel_map.values()
        )
        self.bot.extension_states.relay = munch.Munch()
        self.bot.extension_states.relay.channels = self.listen_channels

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        if not channel.id in self.listen_channels:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message:
            return

        if message.author.bot:
            return

        edit_event = MessageEditEvent(message.author, channel, message=message)

        await self.publish(edit_event.to_json(), message.guild)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        if payload.member.bot:
            return

        if not channel.id in self.listen_channels:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message or not message.content:
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
        if not ctx.channel.id in self.listen_channels:
            return False
        return True

    async def response(self, _, ctx, __, ___):
        message_event = MessageEvent(
            ctx.author,
            ctx.channel,
            message=ctx.message,
        )
        await message_event.fill_reply_data()
        await self.publish(message_event.to_json(), ctx.message.guild)

    async def publish(self, payload, guild):
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


class IRCReceiver(base.LoopCog):

    IRC_LOGO = "📨"
    # start the receiver right away
    ON_START = True

    async def loop_preconfig(self):
        self.listen_channels = list(
            self.bot.file_config.special.relay.channel_map.values()
        )

    async def execute(self, _config, guild):
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
                f"Could not consume IRC event from relay broker (will restart consuming in {self.DEFAULT_WAIT} seconds)",
                send=True,
                exception=e,
            )

    async def handle_event(self, response):
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

        channel = self._get_channel(data)
        if not channel:
            return

        await channel.send(embed=embed)

    @staticmethod
    def _add_mentions(message, guild, channel):
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

    def _get_channel(self, data):
        for channel_id in self.listen_channels:
            if channel_id == self.bot.file_config.special.relay.channel_map.get(
                data.channel.name
            ):
                return self.bot.get_channel(int(channel_id))

    def deserialize(self, body):
        deserialized = munch.Munch.fromJSON(body)

        time = deserialized.event.time
        if not time:
            return
        if self._time_stale(time):
            return

        return deserialized

    def _time_stale(self, time):
        time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        if (
            now - time
        ).total_seconds() > self.bot.file_config.special.relay.stale_seconds:
            return True

        return False

    def process_embed(self, data):
        if data.event.type == "message":
            return IRCMessageEmbed(data=data)
        return IRCEventEmbed(data=data)

    def process_message(self, data):
        if data.event.type == "message":
            return self._format_chat_message(data)

        return self._format_event_message(data)

    def _format_chat_message(self, data):
        return f"{self.IRC_LOGO} `{self._get_permissions_label(data.author.permissions)}{data.author.nickname}` {data.event.content}"

    def _format_event_message(self, data):
        permissions_label = self._get_permissions_label(data.author.permissions)
        if data.event.type == "join":
            return f"{self.IRC_LOGO} `{permissions_label}{data.author.mask}` has joined {data.channel.name}!"

        elif data.event.type == "part":
            return f"{self.IRC_LOGO} `{permissions_label}{data.author.mask}` left {data.channel.name}!"

        elif data.event.type == "quit":
            return f"{self.IRC_LOGO} `{permissions_label}{data.author.mask}` quit ({data.event.content})"

        elif data.event.type == "kick":
            return f"{self.IRC_LOGO} `{permissions_label}{data.author.mask}` kicked `{data.event.target}` from {data.channel.name}! (reason: *{data.event.content}*)."

        elif data.event.type == "action":
            # this isnt working well right now
            return f"{self.IRC_LOGO} `{permissions_label}{data.author.nickname}` {data.event.content}"

        elif data.event.type == "other":
            if data.event.irc_command.lower() == "mode":
                return f"{self.IRC_LOGO} `{permissions_label}{data.author.nickname}` sets mode **{data.event.irc_paramlist[1]}** on `{data.event.irc_paramlist[2]}`"
            else:
                return f"{self.IRC_LOGO} `{data.author.mask}` did some configuration on {data.channel.name}..."

    @staticmethod
    def _get_permissions_label(permissions):
        label = ""
        if permissions:
            if "v" in permissions:
                label += "+"
            if "o" in permissions:
                label += "@"

        return label
