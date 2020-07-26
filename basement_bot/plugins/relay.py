import datetime
import json
import logging
import re

import pika

from cogs import LoopPlugin, MatchPlugin
from utils.helpers import get_env_value

logging.getLogger("pika").setLevel(logging.WARNING)


def setup(bot):
    bot.add_cog(DiscordMessageRelay(bot))
    bot.add_cog(IRCMessageReceiver(bot))


class DiscordMessageRelay(MatchPlugin):

    MQ_HOST = get_env_value("RELAY_MQ_HOST")
    QUEUE = get_env_value("RELAY_MQ_SEND_QUEUE")
    CHANNEL_ID = get_env_value("RELAY_CHANNEL")

    def match(self, ctx, content):
        if ctx.channel.id == int(self.CHANNEL_ID):
            if not content.startswith(self.bot.command_prefix):
                return True

    def get_nick_from_id_match(self, match):
        id = int(match.group(1))
        user = self.bot.get_user(id)
        return f"@{user.name}" if user else "@user"

    async def response(self, ctx, content):
        content = re.sub(r"<@?!?(\d+)>", self.get_nick_from_id_match, content)

        mq_connection = pika.BlockingConnection(pika.URLParameters(self.MQ_HOST))
        mq_channel = mq_connection.channel()
        mq_channel.queue_declare(queue=self.QUEUE, durable=True)
        mq_channel.basic_publish(
            exchange="", routing_key=self.QUEUE, body=self.serialize(ctx, content)
        )
        mq_connection.close()

    @staticmethod
    def serialize(ctx, content):
        data = {}
        data["time"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        data["author_name"] = ctx.author.name
        data["author_id"] = ctx.author.id
        data["is_bot"] = ctx.author.bot
        data["channel_name"] = ctx.channel.name
        data["channel_id"] = ctx.channel.id
        data["message"] = content
        return json.dumps(data)


class IRCMessageReceiver(LoopPlugin):

    DEFAULT_WAIT = 1
    MQ_HOST = get_env_value("RELAY_MQ_HOST")
    QUEUE = get_env_value("RELAY_MQ_RECV_QUEUE")
    CHANNEL_ID = get_env_value("RELAY_CHANNEL")

    async def loop_preconfig(self):
        await self.bot.wait_until_ready()
        self.channel = self.bot.get_channel(int(self.CHANNEL_ID))

    async def execute(self):
        mq_connection = pika.BlockingConnection(pika.URLParameters(self.MQ_HOST))
        mq_channel = mq_connection.channel()
        mq_channel.queue_declare(queue=self.QUEUE, durable=True)
        method, _, body = mq_channel.basic_get(queue=self.QUEUE)
        if method:
            mq_channel.basic_ack(method.delivery_tag)
            message = self.deserialize(body)
            if message:
                await self.channel.send(message)
        mq_connection.close()

    @staticmethod
    def deserialize(body):
        try:
            deserialized = json.loads(body)
        except Exception:
            return None

        time = deserialized.get("time")
        if not time:
            return
            
        time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        if (now - time).total_seconds() > 600:
            return

        author_nick = deserialized.get("author_nick")
        message = deserialized.get("message")
        if author_nick and message:
            return f"[IRC] **{author_nick}**: {message}"
