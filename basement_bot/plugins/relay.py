import copy
import datetime
import functools
import json
import logging
import re
import uuid

import base
import decorate
import munch
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[DiscordRelay, IRCReceiver], no_guild=True)


class DiscordRelay(base.MatchCog):
    async def preconfig(self):
        self.channels = list(self.bot.config.special.relay.channel_map.values())
        self.bot.plugin_api.plugins.relay.memory.channels = self.channels

    async def match(self, _, ctx, __):
        if ctx.channel.id in self.channels:
            return True
        return False

    async def response(self, _, ctx, __):
        ctx_data = munch.Munch()

        ctx_data.message = copy.copy(ctx.message)
        ctx_data.author = ctx.author
        ctx_data.channel = ctx.channel

        ctx_data.message.content = self.bot.sub_mentions_for_usernames(
            ctx_data.message.content
        )

        payload = self.serialize("message", ctx_data)

        try:
            await self.bot.rabbit_publish(
                payload, self.bot.config.special.relay.send_queue
            )
        except Exception as e:
            log_channel = await self.bot.get_log_channel_from_guild(
                ctx.guild, "logging_channel"
            )
            await self.bot.logger.error(
                "Could not publish Discord event to relay broker",
                e,
                channel=log_channel,
                critical=True,
            )

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
        data.event.command = None
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
        return as_json


class IRCReceiver(base.LoopCog):

    IRC_LOGO = "📨"
    # start the receiver right away
    ON_START = True

    async def loop_preconfig(self):
        self.channels = list(self.bot.config.special.relay.channel_map.values())

    async def execute(self, _config, _guild):
        try:
            await self.bot.rabbit_consume(
                self.bot.config.special.relay.recv_queue,
                self.handle_event,
                poll_wait=1,
                durable=True,
            )
        except Exception as e:
            log_channel = await self.bot.get_log_channel_from_guild(
                self, ctx.guild, "log_channel"
            )
            await self.bot.logger.error(
                "Could not consume IRC event from relay broker (will restart consuming in {self.DEFAULT_WAIT} seconds)",
                e,
                channel=log_channel,
                critical=True,
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
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                await channel.send(message)

            return

        channel = self._get_channel(data)
        if not channel:
            return

        guild = self.bot.get_guild_from_channel_id(channel.id)

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
            if channel_id == self.bot.config.special.relay.channel_map.get(
                data.channel.name
            ):
                return self.bot.get_channel(channel_id)

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
