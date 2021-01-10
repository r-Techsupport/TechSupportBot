import datetime
import functools
import json
import logging
import re
import uuid

from cogs import LoopPlugin, MatchPlugin, MqPlugin
from discord.ext import commands
from discord.ext.commands import Context
from munch import Munch
from utils.embed import SafeEmbed
from utils.helpers import *
from utils.logger import get_logger

log = get_logger("Relay Plugin")


def setup(bot):
    bot.add_cog(DiscordRelay(bot))
    bot.add_cog(IRCReceiver(bot))


class DiscordRelay(LoopPlugin, MatchPlugin, MqPlugin):

    PLUGIN_NAME = __name__
    WAIT_KEY = "publish_seconds"

    async def preconfig(self):
        self.channels = list(self.config.channel_map.values())
        self.bot.plugin_api.plugins.relay.memory.channels = self.channels
        self.bot.plugin_api.plugins.relay.memory.send_buffer = []
        self.error_message_sent = False

    async def match(self, ctx, content):
        if ctx.channel.id in self.channels:
            return True
        return False

    async def response(self, ctx, content):
        ctx.content = sub_mentions_for_usernames(self.bot, content)
        self.bot.plugin_api.plugins.relay.memory.send_buffer.append(
            self.serialize("message", ctx)
        )

    # main looper
    async def execute(self):
        # grab from buffer
        bodies = [
            body
            for idx, body in enumerate(
                self.bot.plugin_api.plugins.relay.memory.send_buffer
            )
            if idx + 1 <= self.config.send_limit
        ]

        if self.bot.plugin_api.plugins.get(
            "factoids"
        ) and self.bot.plugin_api.plugins.factoids.memory.get("factoid_events"):
            buffer_length = len(
                self.bot.plugin_api.plugins.factoids.memory.factoid_events
            )
            limit = 5 if buffer_length >= 5 else buffer_length
            for ctx in self.bot.plugin_api.plugins.factoids.memory.factoid_events[
                0:limit
            ]:
                bodies.append(self.serialize("factoid", ctx))
            self.bot.plugin_api.plugins.factoids.memory.factoid_events = (
                self.bot.plugin_api.plugins.factoids.memory.factoid_events[limit:]
            )

        if bodies:
            success = self.publish(bodies)
            if not success and self.config.notice_errors:
                # just send to first channel on the map
                channel = self.bot.get_channel(
                    self.config.channel_map.get(list(self.config.channel_map.keys())[0])
                )
                if channel and not self.error_message_sent:
                    await channel.send(
                        "**ERROR**: Unable to connect to relay event queue"
                    )
                    self.error_message_sent = True
                    return

            # remove from buffer
            self.bot.plugin_api.plugins.relay.memory.send_buffer = (
                self.bot.plugin_api.plugins.relay.memory.send_buffer[len(bodies) :]
            )

    @staticmethod
    def serialize(type_, ctx):
        data = Munch()

        # event data
        data.event = Munch()
        data.event.id = str(uuid.uuid4())
        data.event.type = type_
        data.event.time = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )
        data.event.content = getattr(ctx, "content", None)
        data.event.command = getattr(ctx, "irc_command", None)
        data.event.attachments = [
            attachment.url for attachment in ctx.message.attachments
        ]

        # author data
        data.author = Munch()
        data.author.username = ctx.author.name
        data.author.id = ctx.author.id
        data.author.nickname = ctx.author.display_name
        data.author.discriminator = ctx.author.discriminator
        data.author.is_bot = ctx.author.bot
        data.author.top_role = str(ctx.author.top_role)
        # permissions data
        data.author.permissions = Munch()
        discord_permissions = ctx.author.permissions_in(ctx.channel)
        data.author.permissions.kick = discord_permissions.kick_members
        data.author.permissions.ban = discord_permissions.ban_members
        data.author.permissions.unban = discord_permissions.ban_members
        data.author.permissions.admin = discord_permissions.administrator

        # server data
        data.server = Munch()
        data.server.name = ctx.author.guild.name
        data.server.id = ctx.author.guild.id

        # channel data
        data.channel = Munch()
        data.channel.name = ctx.channel.name
        data.channel.id = ctx.channel.id

        # non-lossy
        as_json = data.toJSON()
        log.debug(f"Serialized data: {as_json}")
        return as_json

    @commands.command(
        name="irc",
        brief="Commands for IRC relay",
        descrption="Run a command (eg. kick/ban) on the relayed IRC",
        usage="<command> <arg>",
    )
    async def irc_command(self, ctx, *args):
        if not self.config.commands_allowed:
            await tagged_response(ctx, "Relay cross-chat commands are disabled on my end")
            return

        if ctx.channel.id not in self.channels:
            log.warning(f"IRC command issued outside of allowed channels")
            await tagged_response(
                ctx, "That command can only be used from the IRC relay channels"
            )
            return

        permissions = ctx.author.permissions_in(ctx.channel)

        if len(args) == 0:
            await tagged_response(ctx, "No IRC command provided. Try `.help irc`")
            return

        command = args[0]
        if len(args) == 1:
            await tagged_response(ctx, f"No target provided for IRC command {command}")
            return

        target = " ".join(args[1:])

        ctx.irc_command = command
        ctx.content = target

        await tagged_response(
            ctx,
            f"Sending **{command}** command with target `{target}` to IRC bot...",
        )
        self.bot.plugin_api.plugins.relay.memory.send_buffer.append(
            self.serialize("command", ctx)
        )


class IRCReceiver(LoopPlugin, MqPlugin):

    PLUGIN_NAME = __name__
    WAIT_KEY = "consume_seconds"
    IRC_LOGO = "\U0001F4E8"  # emoji

    async def preconfig(self):
        self.channels = list(self.config.channel_map.values())
        self.error_count = 0
        self.error_message_sent = False

    # main looper
    async def execute(self):
        responses, success = self.consume()
        if not success and self.config.notice_errors:
            # just send to first channel on the map
            channel = self.bot.get_channel(
                self.config.channel_map.get(list(self.config.channel_map.keys())[0])
            )
            if channel and not self.error_message_sent:
                await channel.send("**ERROR**: Unable to connect to relay event queue")
                self.error_message_sent = True
                return

        for response in responses:
            await self.handle_event(response)

    async def handle_event(self, response):
        data = self.deserialize(response)
        if not data:
            log.warning("Unable to deserialize data! Aborting!")
            return

        # handle message event
        if data.event.type in [
            "message",
            "join",
            "part",
            "quit",
            "kick",
            "action",
            "other",
            "factoid",
        ]:

            message = self.process_message(data)
            if message:

                if data.event.type == "quit":
                    for channel_id in self.channels:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            await channel.send(message)
                        else:
                            log.warning("Unable to find channel to send quit event")

                else:
                    channel = self._get_channel(data)
                    if not channel:
                        log.warning("Unable to find channel to send command event")
                        return

                    guild = get_guild_from_channel_id(self.bot, channel.id)

                    if guild:
                        new_message = ""
                        for word in message.split(" "):
                            member = guild.get_member_named(word)
                            if member:
                                new_message += f"{member.mention} "
                            else:
                                new_message += f"{word} "
                        message = new_message

                    await channel.send(message)

                    # perform factoid event if message requested it
                    if data.event.type == "factoid":
                        await self._process_factoid_request(data)

            else:
                log.warning(f"Unable to format message for event: {response}")

        # handle command event
        elif data.event.type == "command":
            await self.process_command(data)

        elif data.event.type == "response":
            await self.process_response(data)

        else:
            log.warning(f"Unable to handle event: {response}")

    async def process_command(self, data):
        if not self.config.commands_allowed:
            log.debug(
                f"Blocking incoming {data.event.command} request due to disabled config"
            )
            return

        if data.event.command in ["kick", "ban", "unban"]:
            await self._process_user_command(data)
        else:
            log.warning(f"Received unroutable command: {data.event.command}")

    async def process_response(self, data):
        response = data.event.content
        if not response:
            log.warning("Received empty response")
            return

        if response.type == "whois":
            await self._process_whois_response(data)
            requester = self.bot.get_user(response.request.author)

    async def _process_whois_response(self, data):
        response = data.event.content
        author_id = response.request.author
        requester = self.bot.get_user(author_id)
        if not requester:
            log.warning(
                f"Unable to find user with ID {author_id} associated with response"
            )
            return
        dm_channel = await requester.create_dm()

        embed = SafeEmbed(title=f"WHOIS Response for {response.payload.nick}")
        embed.add_field(
            name="User", value=response.payload.user or "Not found", inline=False
        )
        embed.add_field(
            name="Host", value=response.payload.host or "Not found", inline=False
        )
        embed.add_field(
            name="Realname",
            value=response.payload.realname or "Not found",
            inline=False,
        )
        embed.add_field(
            name="Server", value=response.payload.server or "Not found", inline=False
        )

        await dm_channel.send(embed=embed)

    @staticmethod
    def _data_has_op(data):
        if "o" not in data.author.permissions:
            return False
        return True

    def _get_channel(self, data):
        for channel_id in self.channels:
            if channel_id == self.config.channel_map.get(data.channel.name):
                return self.bot.get_channel(channel_id)

    async def _process_user_command(self, data):
        if not self._data_has_op(data):
            log.warning(
                f"Blocking incoming {data.event.command} request due to permissions"
            )
            return

        channel = self._get_channel(data)
        if not channel:
            log.warning("Unable to find channel to send command alert")
            return

        await channel.send(
            f"Executing IRC **{data.event.command}** command from `{data.author.mask}` on target `{data.event.content}`"
        )

        target_guild = get_guild_from_channel_id(self.bot, channel.id)
        if not target_guild:
            await channel.send(f"> Critical error! Aborting command")
            log.warning(
                f"Unable to find guild associated with relay channel (this is unusual)"
            )
            return

        target_user = target_guild.get_member_named(data.event.content)
        if not target_user:
            await channel.send(
                f"Unable to locate target `{data.event.content}`! Aborting command"
            )
            return

        # very likely this will raise an exception :(
        if data.event.command == "kick":
            await target_guild.kick(target_user)
        elif data.event.command == "ban":
            await target_guild.ban(target_user, self.config.discord_ban_days)
        elif data.event.command == "unban":
            await target_guild.unban(target_user)

    def deserialize(self, body):
        deserialized = Munch.fromJSON(body)

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
        else:
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

    async def _process_factoid_request(self, data):
        factoid_plugin = self.bot.cogs.get("FactoidManager")
        if not factoid_plugin:
            log.warning(
                "Factoid request processer called when Factoid plugin not loaded"
            )
            return

        # (this approach is hackier than I prefer)
        channel = self._get_channel(data)
        message = await channel.send(data.event.content)
        ctx = await self.bot.get_context(message)

        await factoid_plugin.response(ctx, data.event.content)

        await message.delete()
