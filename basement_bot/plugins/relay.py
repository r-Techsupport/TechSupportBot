import datetime
import json
import logging

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

    async def preconfig(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(self.MQ_HOST))
        self.mq_channel = self.connection.channel()
        self.mq_channel.queue_declare(queue=self.QUEUE, durable=True)

    def match(self, ctx, _):
        if ctx.channel.id == int(self.CHANNEL_ID):
            return True

    async def response(self, ctx, content):
        self.mq_channel.basic_publish(
            exchange="", routing_key=self.QUEUE, body=self.serialize(ctx, content)
        )

    @staticmethod
    def serialize(ctx, content):
        data = {}
        data["time"] = datetime.datetime.now()
        data["author_name"] = ctx.author.name
        data["author_id"] = ctx.author.id
        data["is_bot"] = ctx.author.bot
        data["channel_name"] = ctx.channel.name
        data["channel_id"] = ctx.channel.id
        data["message"] = content
        return json.dumps(data, default=str)


class IRCMessageReceiver(LoopPlugin):

    DEFAULT_WAIT = 1
    MQ_HOST = get_env_value("RELAY_MQ_HOST")
    QUEUE = get_env_value("RELAY_MQ_RECV_QUEUE")
    CHANNEL_ID = get_env_value("RELAY_CHANNEL")

    async def loop_preconfig(self):
        self.connection = pika.BlockingConnection(pika.URLParameters(self.MQ_HOST))
        self.mq_channel = self.connection.channel()
        self.mq_channel.queue_declare(queue=self.QUEUE, durable=True)
        await self.bot.wait_until_ready()
        self.channel = self.bot.get_channel(int(self.CHANNEL_ID))

    async def execute(self):
        method, header, body = self.mq_channel.basic_get(queue=self.QUEUE)
        if method:
            self.mq_channel.basic_ack(method.delivery_tag)
            message = self.deserialize(body)
            if message:
                await self.channel.send(message)

    @staticmethod
    def deserialize(body):
        try:
            deserialized = json.loads(body)
        except Exception:
            return None

        time = deserialized.get("time")
        author_nick = deserialized.get("author_nick")
        message = deserialized.get("message")
        if author_nick and message and time:
            time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S.%f")
            time = time.strftime("%H:%M:%S")
            return f"[IRC@{time}] **{author_nick}**: {message}"
