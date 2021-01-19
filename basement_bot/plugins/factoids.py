import asyncio
import datetime
import json

from cogs import DatabasePlugin, LoopPlugin, MatchPlugin
from decorate import with_typing
from discord import HTTPException
from discord.ext import commands
from logger import get_logger
from sqlalchemy import Column, DateTime, Integer, String

log = get_logger("Factoids")


class Factoid(DatabasePlugin.BaseTable):
    __tablename__ = "factoids"

    pk = Column(Integer, primary_key=True)
    text = Column(String)
    channel = Column(String)
    message = Column(String)
    time = Column(DateTime, default=datetime.datetime.utcnow)
    embed_config = Column(String, default=None)
    loop_config = Column(String, default=None)


def setup(bot):
    bot.add_cog(FactoidManager(bot))


class FactoidManager(DatabasePlugin, MatchPlugin, LoopPlugin):

    PLUGIN_NAME = __name__
    MODEL = Factoid
    EXAMPLE_JSON = """
    {
        "color": 16747116,
        "author": {
            "name": "Crystal Disk Info",
            "icon_url": "https://cdn.icon-icons.com/icons2/10/PNG/256/savedisk_floppydisk_guardar_1543.png"
        },
        "fields": [
            {
                "name": "1. To check hard drive health, download Crystal Disk Info (CDI):",
                "value": "https://osdn.net/projects/crystaldiskinfo/downloads/73319/CrystalDiskInfo8_7_0.exe"
            },
            {
                "name": "2. At the top of the programs window, copy the contents ",
                "value": "`Edit` -> `Copy`"
            },
            {
                "name": "3. Publish the results in a Pastebin",
                "value": "https://pastebin.com"
            }
        ]
    }"""
    MATCH_PERMISSIONS = ["send_messages"]
    CACHE_UPDATE_MINUTES = 10

    async def db_preconfig(self):
        factoid_prefix = self.config.prefix
        command_prefix = self.bot.config.main.required.command_prefix

        self.bot.plugin_api.plugins.factoids.memory.factoid_events = []

        if factoid_prefix == command_prefix:
            raise RuntimeError(
                f"Command prefix '{command_prefix}' cannot equal Factoid prefix"
            )

    async def loop_preconfig(self):
        self.loop_jobs = {}
        self.load_jobs()
        self.cache_update_time = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=self.config.loop_update_minutes
        )

    def get_all_factoids(self):
        db = self.db_session()

        factoids = db.query(Factoid).order_by(Factoid.text).all()

        for factoid in factoids:
            db.expunge(factoid)
        db.close()

        return factoids or []

    def get_factoid_from_query(self, query, db=None):
        db = self.db_session()

        factoid = db.query(Factoid).filter(Factoid.text == query).first()

        if factoid:
            db.expunge(factoid)
        db.close()

        return factoid

    def get_embed_from_factoid(self, factoid):
        if not factoid.embed_config:
            return None

        embed_config = json.loads(factoid.embed_config)

        return self.bot.embed_api.Embed.from_dict(embed_config)

    async def add_factoid(self, ctx, **kwargs):
        db = self.db_session()

        # first check if key already exists
        factoid = (
            db.query(Factoid).filter(Factoid.text == kwargs.get("trigger")).first()
        )
        if factoid:
            # delete old one
            db.delete(factoid)
            await self.bot.h.tagged_response(
                ctx, "Deleting previous entry of factoid..."
            )

        trigger = kwargs.get("trigger")
        # finally, add new entry
        db.add(
            Factoid(
                text=trigger,
                channel=kwargs.get("channel"),
                message=kwargs.get("message"),
                embed_config=kwargs.get("embed_config"),
            )
        )
        db.commit()
        db.close()

        await self.bot.h.tagged_response(ctx, f"Successfully added factoid *{trigger}*")

    async def delete_factoid(self, ctx, trigger):
        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == trigger).first()
        if not entry:
            await self.bot.h.tagged_response(ctx, "I couldn't find that factoid")
        else:
            db.delete(entry)
            db.commit()

        db.close()

        await self.bot.h.tagged_response(
            ctx, f"Successfully deleted factoid factoid: *{trigger}*"
        )

    async def match(self, _, content):
        return content.startswith(self.config.prefix)

    async def response(self, ctx, arg):
        query = arg[1:]
        user_mentioned = None
        if len(ctx.message.mentions) == 1:
            # tag this user instead of the caller
            user_mentioned = ctx.message.mentions[0]
            query = query.split(" ")[0]
        elif len(ctx.message.mentions) > 1:
            await self.bot.h.tagged_response(
                ctx, "I can only tag one user when referencing a factoid!"
            )
            return

        factoid = self.get_factoid_from_query(query)

        if not factoid:
            return

        embed = self.get_embed_from_factoid(factoid)

        content = factoid.message if not embed else None

        message = await self.bot.h.tagged_response(
            ctx, content=content, embed=embed, target=user_mentioned
        )

        if not message:
            await self.bot.h.tagged_response(ctx, "I was unable to render that factoid")

        if not self.bot.plugin_api.plugins.get("relay"):
            return

        self.dispatch_relay_factoid(ctx, factoid.message)

    def dispatch_relay_factoid(self, ctx, message):
        # add to the relay plugin queue if it's loaded
        if not ctx.channel.id in self.bot.plugin_api.plugins.relay.memory.channels:
            return

        ctx.content = message

        self.bot.plugin_api.plugins.factoids.memory.factoid_events.append(ctx)

        while len(self.bot.plugin_api.plugins.factoids.memory.factoid_events) > 10:
            del self.bot.plugin_api.plugins.factoids.memory.factoid_events[0]

    def load_jobs(self):
        factoids = self.get_all_factoids()

        if not factoids:
            return

        factoid_set = set()
        for factoid in factoids:
            factoid_set.add(factoid.text)
            self.configure_job(factoid)

        # remove jobs for deleted factoids
        for looped_factoid_key in self.loop_jobs.keys():
            if not looped_factoid_key in factoid_set:
                del self.loop_jobs[looped_factoid_key]

    def configure_job(self, factoid):
        old_loop_config = self.loop_jobs.get(factoid.text, {})

        if not factoid.loop_config:
            # delete stale job
            if old_loop_config:
                del self.loop_jobs[factoid.text]
            return

        loop_config = {}
        sleep_duration = None
        try:
            loop_config = json.loads(factoid.loop_config)
            sleep_duration = int(loop_config.get("sleep_duration"))
        except Exception:
            return

        new_finish_time = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=sleep_duration
        )
        if not old_loop_config or sleep_duration != int(
            old_loop_config.get("sleep_duration", -1)
        ):
            # there is no previous loop config
            # OR
            # the new sleep duration is different than the old one in the job
            # therefore restart the waiting
            loop_config["finish_time"] = new_finish_time
        else:
            loop_config["finish_time"] = old_loop_config.get(
                "finish_time", new_finish_time
            )

        self.loop_jobs[factoid.text] = loop_config

    async def execute(self):
        compare_time = datetime.datetime.utcnow()

        if compare_time > self.cache_update_time:
            self.load_jobs()
            self.cache_update_time = datetime.datetime.utcnow() + datetime.timedelta(
                minutes=self.config.loop_update_minutes
            )

        for factoid_key, loop_config in self.loop_jobs.items():
            finish_time = loop_config.get("finish_time")
            if not finish_time or compare_time < finish_time:
                continue

            channel = None
            sleep_duration = None
            factoid = self.get_factoid_from_query(factoid_key)

            embed = self.get_embed_from_factoid(factoid)
            content = factoid.message if not embed else None

            try:
                sleep_duration = int(loop_config.get("sleep_duration"))
            except Exception:
                continue

            for channel_id in loop_config.get("channel_ids", []):
                try:
                    channel = self.bot.get_channel(int(channel_id))
                    # update time of next message
                    loop_config[
                        "finish_time"
                    ] = datetime.datetime.utcnow() + datetime.timedelta(
                        minutes=sleep_duration
                    )
                    message = await channel.send(content=content, embed=embed)

                    context = await self.bot.get_context(message)

                    self.dispatch_relay_factoid(context, factoid.message)
                except Exception:
                    continue

    # main clock for looping
    async def wait(self):
        await asyncio.sleep(60)

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Creates a factoid",
        description=(
            "Creates a custom factoid with a specified name that outputs any specified text,"
            " including mentions. All factoids are used by sending a message with a '?'"
            " appended in front of the factoid name."
        ),
        usage="[factoid-name] [factoid-output] <optional-embed-json-upload>",
    )
    async def remember(self, ctx, *args):
        if ctx.message.mentions:
            await self.bot.h.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        embed_config = await self.bot.h.get_json_from_attachment(
            ctx, ctx.message, send_msg_on_none=False, send_msg_on_failure=False
        )
        if embed_config:
            embed_config = json.dumps(embed_config)
        elif embed_config == {}:
            return

        if len(args) < 2:
            await self.bot.h.tagged_response(
                ctx, "Provide a trigger and a default message"
            )
            return

        trigger = args[0].lower()
        message = " ".join(args[1:])

        if not trigger or not message:
            await self.bot.h.tagged_response(ctx, "Invalid trigger/message")
            return

        channel = getattr(ctx.message, "channel", None)
        channel = str(channel.id) if channel else None

        await self.add_factoid(
            ctx,
            trigger=trigger,
            channel=channel,
            message=message,
            embed_config=embed_config,
        )

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Deletes a factoid",
        description="Deletes a factoid permanently",
        usage="[factoid-name]",
    )
    async def forget(self, ctx, *args):
        if ctx.message.mentions:
            await self.bot.h.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        if not args:
            await self.bot.h.tagged_response(
                ctx, "You must specify a factoid to delete!"
            )
            return

        await self.delete_factoid(ctx, args[0])

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Loops a factoid",
        description="Loops a pre-existing factoid",
        usage="[factoid-name] [sleep_duration (minutes)] [channel_id] [channel_id_2] ...",
    )
    async def setup_loop(self, ctx, factoid_name, sleep_duration, *channel_ids):
        if not channel_ids:
            await self.bot.h.tagged_response(
                ctx, "Please provide at least one valid channel ID"
            )
            return

        # I really need to start using converters
        if any(
            self.bot.get_channel(int(id)) is None if id.isnumeric() else True
            for id in channel_ids
        ):
            await self.bot.h.tagged_response(
                ctx, "One or more of those channel ID's is not valid"
            )
            return

        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == factoid_name).first()
        if not entry:
            await self.bot.h.tagged_response(ctx, "I couldn't find that factoid")
            return db.close()

        if entry.loop_config:
            await self.bot.h.tagged_response(
                ctx, "Deleting previous loop configuration..."
            )

        entry.loop_config = json.dumps(
            {"sleep_duration": sleep_duration, "channel_ids": channel_ids}
        )

        db.commit()
        db.close()

        await self.bot.h.tagged_response(
            ctx, f"Successfully saved loop config for {factoid_name}"
        )

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Removes a factoid's loop config",
        description="De-loops a pre-existing factoid",
        usage="[factoid-name]",
    )
    async def delete_loop(self, ctx, factoid_name):
        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == factoid_name).first()
        if not entry:
            await self.bot.h.tagged_response(ctx, "I couldn't find that factoid")
            return db.close()

        if not entry.loop_config:
            await self.bot.h.tagged_response(
                ctx, "There is no loop config for that factoid"
            )
            return db.close()

        entry.loop_config = None

        db.commit()
        db.close()

        await self.bot.h.tagged_response(ctx, "Loop config deleted")

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Displays the loop config",
        description="Retrieves and displays the loop config for a specific factoid",
        usage="[factoid-name]",
    )
    async def loop_config(self, ctx, factoid_name):
        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == factoid_name).first()
        if entry:
            db.expunge(entry)
        db.close()

        if not entry:
            await self.bot.h.tagged_response(ctx, "I couldn't find that factoid")
            return

        if not entry.loop_config:
            await self.bot.h.tagged_response(
                ctx, "There is no loop config for that factoid"
            )
            return

        try:
            loop_config = json.loads(entry.loop_config)
        except Exception:
            await self.bot.h.tagged_response(
                ctx, "I couldn't process the JSON for that loop config"
            )
            return

        embed_label = ""
        if entry.embed_config:
            embed_label = "(embed)"

        embed = self.bot.embed_api.Embed(
            title=f"Loop config for {factoid_name} {embed_label}",
            description=f'"{entry.message}"',
        )

        sleep_duration = loop_config.get("sleep_duration", "???")
        embed.add_field(
            name="Sleep duration", value=f"{sleep_duration} minute(s)", inline=False
        )

        channel_ids = loop_config.get("channel_ids", [])
        # check this shit out
        channels = [
            "#" + getattr(self.bot.get_channel(int(channel_id)), "name", "???")
            for channel_id in channel_ids
        ]
        embed.add_field(name="Channels", value=", ".join(channels), inline=False)

        embed.add_field(
            name="Next execution (UTC)",
            value=self.loop_jobs.get(factoid_name, {}).get("finish_time", "???"),
        )

        await self.bot.h.tagged_response(ctx, embed=embed)

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="lsf",
        brief="List all factoids",
        description="Shows an embed with all the factoids",
    )
    async def list_all_factoids(self, ctx):
        if ctx.message.mentions:
            await self.bot.h.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        factoids = self.get_all_factoids()
        if not factoids:
            await self.bot.h.tagged_response(ctx, "No factoids found!")
            return

        field_counter = 1
        embeds = []
        for index, factoid in enumerate(factoids):
            embed = (
                self.bot.embed_api.Embed(
                    title="Factoids",
                    description=f"Access factoids with the `{self.config.prefix}` prefix",
                )
                if field_counter == 1
                else embed
            )

            label_addon = []
            if factoid.embed_config:
                label_addon.append("(embed)")
            if factoid.loop_config:
                label_addon.append("(loop)")

            label = " ".join(label_addon)

            embed.add_field(
                name=f"{factoid.text} {label}",
                value=factoid.message,
                inline=False,
            )
            if field_counter == self.config.list_all_max or index == len(factoids) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        self.bot.h.task_paginate(ctx, embeds=embeds, restrict=True)

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Gets raw factoid data",
        description="Gets (cats) the raw data of a factoid object",
        usage="[factoid-name]",
    )
    async def embed_config(self, ctx, *args):
        if not args:
            await self.bot.h.tagged_response(
                ctx, f"(Example) ```{self.EXAMPLE_JSON}```"
            )
            return

        factoid = self.get_factoid_from_query(args[0])

        if not factoid:
            await self.bot.h.tagged_response(ctx, "I couldn't find that factoid")
            return

        if not factoid.embed_config:
            await self.bot.h.tagged_response(
                ctx, "There is no embed config for that factoid"
            )
            return

        formatted = json.dumps(factoid.embed_config, indent=4)

        await self.bot.h.tagged_response(ctx, f"```{formatted}```")

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="loop_jobs",
        brief="Lists loop jobs",
        description="Lists all the currently cached loop jobs",
    )
    async def get_loop_jobs(self, ctx):
        if not self.loop_jobs:
            await self.bot.h.tagged_response(
                ctx,
                f"There are no currently running factoid loops (next cache update: {self.cache_update_time} UTC)",
            )
            return

        embed_kwargs = {}
        for factoid_name, loop_config in self.loop_jobs.items():
            finish_time = loop_config.get("finish_time", "???")
            embed_kwargs[factoid_name] = f"Next execution: {finish_time} UTC"

        embed = self.bot.h.embed_from_kwargs(
            title="Running factoid loops",
            description=f"Next cache update: {self.cache_update_time} UTC",
            **embed_kwargs,
        )

        await self.bot.h.tagged_response(ctx, embed=embed)
