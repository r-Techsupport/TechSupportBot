import datetime
import json
import logging
import re

import pika
from discord.ext import commands
from munch import Munch

from cogs import LoopPlugin, MatchPlugin
from utils.helpers import get_env_value, priv_response
from utils.logger import get_logger

logging.getLogger("pika").setLevel(logging.WARNING)
log = get_logger("Relay Plugin")


def setup(bot):
    bot.add_cog(DiscordRelay(bot))
    bot.add_cog(IRCReceiver(bot))


class MqMixin:

    MQ_HOST = get_env_value("RELAY_MQ_HOST")
    MQ_VHOST = get_env_value("RELAY_MQ_VHOST", default="/")
    MQ_USER = get_env_value("RELAY_MQ_USER")
    MQ_PASS = get_env_value("RELAY_MQ_PASS")
    MQ_PORT = int(get_env_value("RELAY_MQ_PORT"))
    CHANNEL_ID = int(get_env_value("RELAY_CHANNEL"))
    
    QUEUE = None

    def _get_connection(self):
        try:
            parameters = pika.ConnectionParameters(
                self.MQ_HOST,
                self.MQ_PORT,
                self.MQ_VHOST,
                pika.PlainCredentials(self.MQ_USER, self.MQ_PASS)
            )
            return pika.BlockingConnection(parameters)
        except Exception as e:
            e = str(e) or "No route to host"  # dumb correction to a blank error
            log.warning(f"Unable to connect to RabbitMQ: {e}")

    def publish(self, body):
        try:
            mq_connection = self._get_connection()
            if not mq_connection:
                log.warning(
                    f"Unable to retrieve MQ connection - aborting publish: {body}"
                )
                return
            mq_channel = mq_connection.channel()
            mq_channel.queue_declare(queue=self.QUEUE, durable=True)
            mq_channel.basic_publish(exchange="", routing_key=self.QUEUE, body=body)
            mq_connection.close()
        except Exception as e:
            log.warning(f"Unable to publish body to queue {SEND_QUEUE}: {e}")

    def consume(self):
        try:
            mq_connection = self._get_connection()
            if not mq_connection:
                log.warning(f"Unable to retrieve MQ connection - aborting consume")
                return
            mq_channel = mq_connection.channel()
            mq_channel.queue_declare(queue=self.QUEUE, durable=True)
            method, _, body = mq_channel.basic_get(queue=self.QUEUE)
            if method:
                mq_channel.basic_ack(method.delivery_tag)
                mq_connection.close()
                return body
        except Exception as e:
            log.warning(f"Unable to consume from queue {RECV_QUEUE}: {e}")


class IrcFormatMixin:

    IRC_LOGO = "**[IRC]**"

    def format_message(self, data):
        if data.event.type == "message":
            return self._format_chat_message(data)
        else:
            return self._format_event_message(data)

    @staticmethod
    def _get_permissions_label(permissions):
        return "@" if permissions.op else ""

    def _format_chat_message(self, data):
        return f"{self.IRC_LOGO} *{self._get_permissions_label(data.permissions)}{data.author.nickname}*: {data.event.content}"

    def _format_event_message(self, data):
        permissions_label = self._get_permissions_label(data.permissions)
        if data.event.type == "join":
            return f"{self.IRC_LOGO} *{permissions_label}{data.author.mask}* has joined {data.channel.name}!"
        elif data.event.type == "part":
            return f"{self.IRC_LOGO} *{permissions_label}{data.author.mask}* left {data.channel.name}!"
        elif data.event.type == "kick":
            return f"{self.IRC_LOGO} *{permissions_label}{data.author.mask}* kicked *{data.event.target}* from {data.channel.name}! (reason: *{data.event.content}*)."
        elif data.event.type == "action":
            # this isnt working well right now
            return f"{self.IRC_LOGO} *{permissions_label}{data.author.nickname}* {data.event.content}"
        elif data.event.type == "other":
            return f"{self.IRC_LOGO} *{data.author.mask}* did some configuration on {data.channel.name}..."


class DiscordRelay(MatchPlugin, MqMixin):

    QUEUE = get_env_value("RELAY_MQ_SEND_QUEUE")

    def match(self, ctx, content):
        if ctx.channel.id == self.CHANNEL_ID:
            if not content.startswith(self.bot.command_prefix):
                return True
        return False

    async def response(self, ctx, content):
        # subs in actual mentions if possible
        ctx.content = re.sub(r"<@?!?(\d+)>", self._get_nick_from_id_match, content)
        self.publish(self.serialize("message", ctx))

    @commands.command(
        name="irc",
        brief="Commands for IRC relay",
        descrption="Run a command (eg. kick/ban) on the relayed IRC",
        usage="<command> <arg>",
    )
    async def irc_command(self, ctx, *args):
        if ctx.channel.id != self.CHANNEL_ID:
            log.debug(f"IRC command issued outside of channel ID {self.CHANNEL_ID}")
            await priv_response(
                ctx, "That command can only be used from the IRC relay channel."
            )
            return

        permissions = ctx.author.permissions_in(ctx.channel)

        if len(args) > 0:
            command = args[0]
            if command in ["kick", "ban", "unban"] and len(args) > 1:

                permissions = ctx.author.permissions_in(ctx.channel)
                if (
                    command == "kick"
                    and not (permissions.kick_members or permissions.administrator)
                ) or (
                    command in ["ban", "unban"]
                    and not (permissions.ban_members or permissions.administrator)
                ):
                    log.warning(
                        f"Unauthorized IRC command issued by {ctx.message.author.name}"
                    )
                    await priv_response(
                        ctx, f"You do not have permission to issue that relay command"
                    )
                    return

                target = args[1]
                ctx.irc_command = command
                ctx.content = target
                await priv_response(
                    ctx,
                    f"Sending `{command}` command with target `{target}` to IRC bot...",
                )
                self.publish(self.serialize("command", ctx))

    @staticmethod
    def serialize(type_, ctx):
        data = Munch()

        # event data
        data.event = Munch()
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

        # server data
        data.server = Munch()
        data.server.name = ctx.author.guild.name
        data.server.id = ctx.author.guild.id

        # channel data
        data.channel = Munch()
        data.channel.name = ctx.channel.name
        data.channel.id = ctx.channel.id

        # permissions data
        data.permissions = Munch()
        discord_permissions = ctx.author.permissions_in(ctx.channel)
        data.permissions.kick = discord_permissions.kick_members
        data.permissions.ban = discord_permissions.ban_members
        data.permissions.admin = discord_permissions.administrator

        # non-lossy
        as_json = data.toJSON()
        log.debug(f"Serialized data: {as_json}")
        return as_json

    def _get_nick_from_id_match(self, match):
        id = int(match.group(1))
        user = self.bot.get_user(id)
        return f"@{user.name}" if user else "@user"


class IRCReceiver(LoopPlugin, MqMixin, IrcFormatMixin):

    DEFAULT_WAIT = int(get_env_value("RELAY_CONSUME_SECONDS"))
    QUEUE = get_env_value("RELAY_MQ_RECV_QUEUE")
    BAN_PERIOD_DAYS = int(get_env_value("RELAY_DISCORD_BAN_DAYS"))
    STALE_PERIOD_SECONDS = int(get_env_value("RELAY_STALE_SECONDS"))

    async def loop_preconfig(self):
        await self.bot.wait_until_ready()
        self.channel = self.bot.get_channel(self.CHANNEL_ID)

    async def execute(self):
        response = self.consume()
        if response:
            await self.handle_event(response)

    async def handle_event(self, response):
        data = self.deserialize(response)
        if not data:
            log.warning("Unable to deserialize data! Aborting!")
            return

        # handle message event
        if data.event.type in ["message", "join", "part", "kick", "action", "other"]:
            message = self.format_message(data)
            if message:
                await self.channel.send(message)
            else:
                log.warning(f"Unable to format message for event: {response}")

        # handle command event
        elif data.event.type == "command":
            await self.process_command(data)

        else:
            log.warning(f"Unable to handle event: {response}")

    async def process_command(self, data):
        # server-side permissions check
        if not getattr(data.permissions, "op") == True:
            log.debug(f"Blocking incoming {data.event.command} request")
            return

        await self.channel.send(
            f"Executing IRC `{data.event.command}` command from *{data.author.mask}* on target *{data.event.content}*"
        )

        target_guild = None
        for guild in self.bot.guilds:
            for channel in guild.channels:
                if channel.id == self.channel.id:
                    target_guild = guild

        if not target_guild:
            await self.channel.send(f"> Critical error! Aborting command")
            log.warning(
                f"Unable to find guild associated with relay channel (this is unusual)"
            )
            return

        target_user = target_guild.get_member_named(data.event.content)
        if not target_user:
            await self.channel.send(
                f"Unable to locate target *{data.event.content}*! Aborting command"
            )
            return
            # log.warning(f"Unable to find user associated with {data.event.command} target {data.event.content}")

        # route appropriately
        if data.event.command == "kick":
            await target_guild.kick(target_user)
        elif data.event.command == "ban":
            await target_guild.ban(target_user, self.BAN_PERIOD_DAYS)
        elif data.event.command == "unban":
            await target_guild.unban(target_user)
        else:
            log.warning(f"Received unroutable command: {data.event.command}")

    def deserialize(self, body):
        try:
            deserialized = Munch.fromJSON(body)
        except Exception:
            log.warning(f"Unable to Munch-deserialize incoming data")
            return

        time = deserialized.event.time
        if not time:
            log.warning(f"Unable to retrieve time object from incoming data")
            return
        if self.time_stale(time):
            log.warning(
                f"Incoming data failed stale check ({self.STALE_PERIOD_SECONDS} seconds)"
            )
            return

        log.debug(f"Deserialized data: {body})")
        return deserialized

    def time_stale(self, time):
        time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        if (now - time).total_seconds() > self.STALE_PERIOD_SECONDS:
            return True
        return False
