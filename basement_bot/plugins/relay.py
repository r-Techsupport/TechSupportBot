import datetime
import functools
import json
import logging
import re
import uuid

import aio_pika
import cogs
import decorate
import logger
import munch
from discord.ext import commands

log = logger.get_logger("Relay Plugin")


def setup(bot):
    bot.add_cog(DiscordRelay(bot))
    bot.add_cog(IRCReceiver(bot))


class DiscordRelay(cogs.MatchPlugin):

    async def preconfig(self):
        self.channels = list(self.config.channel_map.values())
        self.bot.plugin_api.plugins.relay.memory.channels = self.channels

        self.connection = await aio_pika.connect_robust(
            self.bot.generate_amqp_url(), loop=self.bot.loop
        )

    async def match(self, ctx, _):
        if ctx.channel.id in self.channels:
            return True
        return False

    async def response(self, ctx, _):
        ctx.message.content = self.sub_mentions_for_usernames(ctx.message.content)

        payload = self.serialize("message", ctx)

        await self.publish(payload)

    async def publish(self, payload):
        channel = await self.connection.channel()

        await channel.default_exchange.publish(
            aio_pika.Message(body=payload.encode()), routing_key=self.config.send_queue
        )

        await channel.close()

    @staticmethod
    def serialize(type_, ctx):
        data = munch.Munch()

        # event data
        data.event = munch.Munch()
        data.event.id = str(uuid.uuid4())
        data.event.type = type_
        data.event.time = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )
        data.event.content = ctx.message.content
        data.event.command = getattr(ctx, "irc_command", None)
        data.event.attachments = [
            attachment.url for attachment in ctx.message.attachments
        ]

        # author data
        data.author = munch.Munch()
        data.author.username = ctx.author.name
        data.author.id = ctx.author.id
        data.author.nickname = ctx.author.display_name
        data.author.discriminator = ctx.author.discriminator
        data.author.is_bot = ctx.author.bot
        data.author.top_role = str(ctx.author.top_role)

        # permissions data
        data.author.permissions = munch.Munch()
        discord_permissions = ctx.author.permissions_in(ctx.channel)
        data.author.permissions.kick = discord_permissions.kick_members
        data.author.permissions.ban = discord_permissions.ban_members
        data.author.permissions.unban = discord_permissions.ban_members
        data.author.permissions.admin = discord_permissions.administrator

        # server data
        data.server = munch.Munch()
        data.server.name = ctx.author.guild.name
        data.server.id = ctx.author.guild.id

        # channel data
        data.channel = munch.Munch()
        data.channel.name = ctx.channel.name
        data.channel.id = ctx.channel.id

        # non-lossy
        as_json = data.toJSON()
        log.debug(f"Serialized data: {as_json}")
        return as_json


class IRCReceiver(cogs.BasicPlugin):

    IRC_LOGO = "📨"

    async def preconfig(self):
        self.channels = list(self.config.channel_map.values())
        self.error_count = 0
        self.connection = await aio_pika.connect_robust(self.bot.generate_amqp_url())

        await self.run()

    async def run(self):
        async with self.connection:
            channel = await self.connection.channel()
            queue = await channel.declare_queue(self.config.recv_queue, durable=True)

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        await self.handle_event(message.body.decode())

    async def handle_event(self, response):
        data = self.deserialize(response)
        if not data:
            log.warning("Unable to deserialize data! Aborting!")
            return

        if not data.event.type in ["message", "join", "part", "quit", "kick", "action"]:
            log.warning(f"Unable to handle event: {response}")
            return

        message = self.process_message(data)
        if not message:
            log.warning(f"Unable to format message for event: {response}")
            return

        if data.event.type == "quit":
            for channel_id in self.channels:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    log.warning("Unable to find channel to send quit event")
                    continue
                await channel.send(message)

            return

        channel = self._get_channel(data)
        if not channel:
            log.warning("Unable to find channel to send command event")
            return

        guild = self.get_guild_from_channel_id(channel.id)

        message = self._add_mentions(message, guild)

        await channel.send(message)

    @staticmethod
    def _add_mentions(message, guild):
        new_message = ""
        for word in message.split(" "):
            member = guild.get_member_named(word)
            if member:
                new_message += f"{member.mention} "
            else:
                new_message += f"{word} "

        return new_message

    def _get_channel(self, data):
        for channel_id in self.channels:
            if channel_id == self.config.channel_map.get(data.channel.name):
                return self.bot.get_channel(channel_id)

    def deserialize(self, body):
        deserialized = munch.Munch.fromJSON(body)

        time = deserialized.event.time
        if not time:
            log.warning(f"Unable to retrieve time object from incoming data")
            return
        if self._time_stale(time):
            log.warning(
                f"Incoming data failed stale check ({self.config.stale_seconds} seconds)"
            )
            return

        log.debug(f"Deserialized data: {body})")
        return deserialized

    def _time_stale(self, time):
        time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        if (now - time).total_seconds() > self.config.stale_seconds:
            return True

        return False

    def process_message(self, data):
        if data.event.type in ["message", "factoid"]:
            return self._format_chat_message(data)

        return self._format_event_message(data)

    def _format_chat_message(self, data):
        data.event.content = data.event.content.replace("@everyone", "everyone")
        data.event.content = data.event.content.replace("@here", "here")

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
