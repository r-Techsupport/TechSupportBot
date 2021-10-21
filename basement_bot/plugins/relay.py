import datetime
import uuid

import base
import munch
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[DiscordRelay, IRCReceiver], no_guild=True)


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
        alternate_content = kwargs.pop("content")
        super().__init__("message", *args, **kwargs)
        self.payload.event.content = alternate_content or message.content
        self.payload.event.attachments = [
            attachment.url for attachment in message.attachments
        ]


class MessageEditEvent(MessageEvent):
    pass


class ReactionAddEvent(RelayEvent):
    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        emoji = kwargs.pop("emoji")
        super().__init__("reaction_add", *args, **kwargs)
        self.payload.event.emoji = emoji
        self.payload.event.content = message.content


class DiscordRelay(base.MatchCog):
    async def preconfig(self):
        self.channels = list(self.bot.config.special.relay.channel_map.values())
        self.bot.plugin_api.plugins.relay.memory.channels = self.channels

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        if not channel.id in self.channels:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message:
            return

        if message.author.bot:
            return

        edit_event = MessageEditEvent(
            message.author,
            channel,
            message=message,
            content=f"{message.content}** (message edited)",
        )

        await self.publish(edit_event.to_json(), message.guild)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.member.bot:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        if not channel.id in self.channels:
            return

        message = await channel.fetch_message(payload.message_id)
        if not message:
            return

        emoji = (
            payload.emoji.name
            if payload.emoji.is_unicode_emoji()
            else f":{payload.emoji.name}:"
        )
        reaction_add_event = ReactionAddEvent(
            payload.member, channel, message=message, emoji=emoji
        )

        await self.publish(reaction_add_event.to_json(), message.guild)

    async def match(self, _, ctx, __):
        if ctx.channel.id in self.channels:
            return True
        return False

    async def response(self, _, ctx, __, ___):
        alternate_content = self.bot.sub_mentions_for_usernames(ctx.message.content)
        message_event = MessageEvent(
            ctx.author, ctx.channel, message=ctx.message, content=alternate_content
        )
        await self.publish(message_event.to_json(), ctx.message.guild)

    async def publish(self, payload, guild):
        try:
            await self.bot.rabbit_publish(
                payload, self.bot.config.special.relay.send_queue
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
        self.channels = list(self.bot.config.special.relay.channel_map.values())

    async def execute(self, _config, guild):
        try:
            await self.bot.rabbit_consume(
                self.bot.config.special.relay.recv_queue,
                self.handle_event,
                poll_wait=1,
                durable=True,
            )
        except Exception as e:
            await self.bot.guild_log(
                guild,
                "logging_channel",
                "error",
                "Could not consume IRC event from relay broker (will restart consuming in {self.DEFAULT_WAIT} seconds)",
                send=True,
                exception=e,
            )

    async def handle_event(self, response):
        data = self.deserialize(response)
        if not data:
            return

        if not data.event.type in ["message", "join", "part", "quit", "kick", "action"]:
            return

        message = self.process_message(data)
        if not message:
            return

        if data.event.type == "quit":
            for channel_id in self.channels:
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    continue
                await channel.send(message)

            return

        channel = self._get_channel(data)
        if not channel:
            return

        message = self._add_mentions(message, channel.guild, channel)

        await channel.send(message)

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
        for channel_id in self.channels:
            if channel_id == self.bot.config.special.relay.channel_map.get(
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

        if (now - time).total_seconds() > self.bot.config.special.relay.stale_seconds:
            return True

        return False

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
