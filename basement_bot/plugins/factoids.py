import asyncio
import datetime
import json

import cogs
import decorate
from discord.ext import commands


def setup(bot):
    class Factoid(bot.db.Model):
        __tablename__ = "factoids"

        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        text = bot.db.Column(bot.db.String)
        channel = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        embed_config = bot.db.Column(bot.db.String, default=None)
        loop_config = bot.db.Column(bot.db.String, default=None)

    bot.add_cog(FactoidManager(bot, models=[Factoid]))


class FactoidManager(cogs.MatchCog, cogs.LoopCog):

    CACHE_UPDATE_MINUTES = 10

    async def db_preconfig(self):
        factoid_prefix = self.config.prefix
        command_prefix = self.bot.config.main.required.command_prefix

        if factoid_prefix == command_prefix:
            raise RuntimeError(
                f"Command prefix '{command_prefix}' cannot equal Factoid prefix"
            )

    async def loop_preconfig(self):
        self.loop_jobs = {}
        await self.load_jobs()
        self.cache_update_time = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=self.config.loop_update_minutes
        )

    async def get_all_factoids(self):
        factoids = await self.bot.db.all(self.models.Factoid.query)
        return factoids

    async def get_factoid_from_query(self, query, db=None):
        factoid = await self.models.Factoid.query.where(
            self.models.Factoid.text == query
        ).gino.first()
        return factoid

    def get_embed_from_factoid(self, factoid):
        if not factoid.embed_config:
            return None

        embed_config = json.loads(factoid.embed_config)

        return self.bot.embed_api.Embed.from_dict(embed_config)

    async def add_factoid(self, ctx, **kwargs):
        trigger = kwargs.get("trigger")

        # first check if key already exists
        factoid = await self.get_factoid_from_query(trigger)
        if factoid:
            # delete old one
            await factoid.delete()
            await self.tagged_response(ctx, "Deleting previous entry of factoid...")

        # finally, add new entry
        factoid = self.models.Factoid(
            text=trigger,
            channel=kwargs.get("channel"),
            message=kwargs.get("message"),
            embed_config=kwargs.get("embed_config"),
        )
        await factoid.create()

        await self.tagged_response(ctx, f"Successfully added factoid *{trigger}*")

    async def delete_factoid(self, ctx, trigger):
        factoid = await self.get_factoid_from_query(trigger)
        if not factoid:
            await self.tagged_response(ctx, "I couldn't find that factoid")
            return

        await factoid.delete()
        await self.tagged_response(
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
            await self.tagged_response(
                ctx, "I can only tag one user when referencing a factoid!"
            )
            return

        factoid = await self.get_factoid_from_query(query)

        if not factoid:
            return

        embed = self.get_embed_from_factoid(factoid)

        content = factoid.message if not embed else None

        message = await self.tagged_response(
            ctx, content=content, embed=embed, target=user_mentioned
        )

        if not message:
            await self.tagged_response(ctx, "I was unable to render that factoid")

        await self.dispatch_relay_factoid(ctx, factoid.message)

    async def dispatch_relay_factoid(self, ctx, message):
        relay_cog = self.bot.cogs.get("DiscordRelay")
        if not relay_cog:
            return

        # add to the relay plugin queue if it's loaded
        if not ctx.channel.id in self.bot.plugin_api.plugins.relay.memory.channels:
            return

        ctx.message.content = message

        await relay_cog.response(ctx, message)

    async def load_jobs(self):
        factoids = await self.get_all_factoids()

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
            await self.load_jobs()
            self.cache_update_time = datetime.datetime.utcnow() + datetime.timedelta(
                minutes=self.config.loop_update_minutes
            )

        for factoid_key, loop_config in self.loop_jobs.items():
            finish_time = loop_config.get("finish_time")
            if not finish_time or compare_time < finish_time:
                continue

            channel = None
            sleep_duration = None
            factoid = await self.get_factoid_from_query(factoid_key)

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

    @commands.group(
        brief="Executes a factoid command",
        description="Executes a factoid command",
    )
    async def factoid(self, ctx):
        pass

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @factoid.command(
        brief="Creates a factoid",
        description="Creates a custom factoid with a specified name",
        usage="[factoid-name] [factoid-output] |optional-embed-json-upload|",
    )
    async def remember(self, ctx, factoid_name: str, *, message: str):
        if ctx.message.mentions:
            await self.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        embed_config = await self.get_json_from_attachment(
            ctx, ctx.message, send_msg_on_none=False, send_msg_on_failure=False
        )
        if embed_config:
            embed_config = json.dumps(embed_config)
        elif embed_config == {}:
            return

        await self.add_factoid(
            ctx,
            trigger=factoid_name,
            channel=str(ctx.message.channel.id),
            message=message,
            embed_config=embed_config,
        )

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @factoid.command(
        brief="Deletes a factoid",
        description="Deletes a factoid permanently, including extra config",
        usage="[factoid-name]",
    )
    async def forget(self, ctx, factoid_name: str):
        if ctx.message.mentions:
            await self.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        await self.delete_factoid(ctx, factoid_name)

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @factoid.command(
        brief="Loops a factoid",
        description="Loops a pre-existing factoid",
        usage="[factoid-name] [sleep_duration (minutes)] [channel_id] [channel_id_2] ...",
    )
    async def loop(
        self,
        ctx,
        factoid_name: str,
        sleep_duration: int,
        *channel_ids: commands.Greedy[int],
    ):
        factoid = await self.get_factoid_from_query(factoid_name)
        if not factoid:
            await self.tagged_response(ctx, "I couldn't find that factoid")
            return

        if factoid.loop_config:
            await self.tagged_response(ctx, "Deleting previous loop configuration...")

        new_loop_config = json.dumps(
            {"sleep_duration": sleep_duration, "channel_ids": channel_ids}
        )
        await factoid.update(loop_config=new_loop_config).apply()

        await self.tagged_response(
            ctx, f"Successfully saved loop config for {factoid_name}"
        )

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @factoid.command(
        brief="Removes a factoid's loop config",
        description="De-loops a pre-existing factoid",
        usage="[factoid-name]",
    )
    async def deloop(self, ctx, factoid_name: str):
        factoid = await self.get_factoid_from_query(factoid_name)
        if not factoid:
            await self.tagged_response(ctx, "I couldn't find that factoid")
            return

        if not factoid.loop_config:
            await self.tagged_response(ctx, "There is no loop config for that factoid")
            return

        await factoid.update(loop_config=None).apply()

        await self.tagged_response(ctx, "Loop config deleted")

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @factoid.command(
        brief="Displays loop config",
        description="Retrieves and displays the loop config for a specific factoid",
        usage="[factoid-name]",
    )
    async def job(self, ctx, factoid_name: str):
        factoid = await self.get_factoid_from_query(factoid_name)

        if not factoid:
            await self.tagged_response(ctx, "I couldn't find that factoid")
            return

        if not factoid.loop_config:
            await self.tagged_response(ctx, "There is no loop config for that factoid")
            return

        try:
            loop_config = json.loads(factoid.loop_config)
        except Exception:
            await self.tagged_response(
                ctx, "I couldn't process the JSON for that loop config"
            )
            return

        embed_label = ""
        if factoid.embed_config:
            embed_label = "(embed)"

        embed = self.bot.embed_api.Embed(
            title=f"Loop config for {factoid_name} {embed_label}",
            description=f'"{factoid.message}"',
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

        await self.tagged_response(ctx, embed=embed)

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @factoid.command(
        name="json",
        brief="Gets embed JSON",
        description="Gets embed JSON for a factoid",
        usage="[factoid-name]",
    )
    async def _json(self, ctx, factoid_name: str):
        factoid = await self.get_factoid_from_query(factoid_name)

        if not factoid:
            await self.tagged_response(ctx, "I couldn't find that factoid")
            return

        if not factoid.embed_config:
            await self.tagged_response(ctx, "There is no embed config for that factoid")
            return

        formatted = json.dumps(json.loads(factoid.embed_config), indent=4)

        await self.tagged_response(ctx, f"```{formatted}```")

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @factoid.command(
        brief="Lists loop jobs",
        description="Lists all the currently cached loop jobs",
    )
    async def jobs(self, ctx):
        if not self.loop_jobs:
            await self.tagged_response(
                ctx,
                f"There are no currently running factoid loops (next cache update: {self.cache_update_time} UTC)",
            )
            return

        embed_kwargs = {}
        for factoid_name, loop_config in self.loop_jobs.items():
            finish_time = loop_config.get("finish_time", "???")
            embed_kwargs[factoid_name] = f"Next execution: {finish_time} UTC"

        embed = self.bot.embed_api.Embed.from_kwargs(
            title="Running factoid loops",
            description=f"Next cache update: {self.cache_update_time} UTC",
            **embed_kwargs,
        )

        await self.tagged_response(ctx, embed=embed)

    @decorate.with_typing
    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @factoid.command(
        aliases=["lsf"],
        brief="List all factoids",
        description="Shows an embed with all the factoids",
    )
    async def all(self, ctx):
        if ctx.message.mentions:
            await self.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        factoids = await self.get_all_factoids()
        if not factoids:
            await self.tagged_response(ctx, "No factoids found!")
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

        self.task_paginate(ctx, embeds=embeds, restrict=True)
