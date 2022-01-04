import asyncio
import collections
import datetime
import io
import json

import base
import discord
import expiringdict
import util
import yaml
from discord.ext import commands


def setup(bot):
    class Factoid(bot.db.Model):
        __tablename__ = "factoids"

        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        text = bot.db.Column(bot.db.String)
        channel = bot.db.Column(bot.db.String)
        guild = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        embed_config = bot.db.Column(bot.db.String, default=None)
        loop_config = bot.db.Column(bot.db.String, default=None)
        hidden = bot.db.Column(bot.db.Boolean, default=False)

    config = bot.ExtensionConfig()
    config.add(
        key="manage_roles",
        datatype="list",
        title="Manage factoids roles",
        description="The roles required to manage factoids",
        default=["Factoids"],
    )
    config.add(
        key="per_page",
        datatype="int",
        title="Factoids per page",
        description="The number of factoids per page when retrieving all factoids",
        default=20,
    )

    bot.add_cog(FactoidManager(bot=bot, models=[Factoid], extension_name="factoids"))
    bot.add_extension_config("factoids", config)


async def has_manage_factoids_role(ctx):
    config = await ctx.bot.get_context_config(ctx)
    factoid_roles = []
    for name in config.extensions.factoids.manage_roles.value:
        factoid_role = discord.utils.get(ctx.guild.roles, name=name)
        if not factoid_role:
            continue
        factoid_roles.append(factoid_role)

    if not factoid_roles:
        raise commands.CommandError("no factoid management roles found")

    if not any(
        factoid_role in getattr(ctx.author, "roles", [])
        for factoid_role in factoid_roles
    ):
        raise commands.MissingAnyRole(factoid_roles)

    return True


async def no_mentions(ctx):
    if (
        ctx.message.mention_everyone
        or ctx.message.role_mentions
        or ctx.message.mentions
        or ctx.message.channel_mentions
    ):
        await util.send_deny_embed(
            ctx, "I cannot remember factoids with user/role/channel mentions"
        )
        return False
    return True


class LoopEmbed(discord.Embed):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.blurple()


class FactoidManager(base.MatchCog, base.LoopCog):

    LOOP_UPDATE_MINUTES = 10

    async def preconfig(self):
        self.factoid_cache = expiringdict.ExpiringDict(max_len=100, max_age_seconds=600)

    async def loop_preconfig(self):
        self.loop_jobs = collections.defaultdict(dict)
        await self.bot.logger.info("Loading factoid jobs", send=True)
        await self.load_jobs()
        self.loop_cache_update_time = datetime.datetime.utcnow() + datetime.timedelta(
            minutes=self.LOOP_UPDATE_MINUTES
        )

    async def get_all_factoids(self, guild=None, hide=False):
        if guild and not hide:
            factoids = await self.models.Factoid.query.where(
                self.models.Factoid.guild == str(guild.id)
            ).gino.all()
        elif guild and hide:
            factoids = (
                await self.models.Factoid.query.where(
                    self.models.Factoid.guild == str(guild.id)
                )
                .where(self.models.Factoid.hidden == False)
                .gino.all()
            )
        else:
            factoids = await self.bot.db.all(self.models.Factoid.query)

        if factoids:
            factoids.sort(key=lambda factoid: factoid.text)

        return factoids

    def get_cache_key(self, query, guild):
        return f"{guild.id}_{query}"

    async def get_factoid_from_query(self, query, guild):
        cache_key = self.get_cache_key(query, guild)
        factoid = self.factoid_cache.get(cache_key)
        if not factoid:
            factoid = (
                await self.models.Factoid.query.where(self.models.Factoid.text == query)
                .where(self.models.Factoid.guild == str(guild.id))
                .gino.first()
            )
            self.factoid_cache[cache_key] = factoid
        return factoid

    def get_embed_from_factoid(self, factoid):
        if not factoid.embed_config:
            return None

        embed_config = json.loads(factoid.embed_config)

        return discord.Embed.from_dict(embed_config)

    async def add_factoid(self, ctx, **kwargs):
        trigger = kwargs.get("trigger")

        # first check if key already exists
        factoid = await self.get_factoid_from_query(trigger, ctx.guild)
        if factoid:
            # delete old one
            should_delete = await self.bot.confirm(
                ctx, "This factoid already exists. Should I overwrite it?"
            )
            if not should_delete:
                return
            await factoid.delete()

        # finally, add new entry
        factoid = self.models.Factoid(
            text=trigger,
            channel=kwargs.get("channel"),
            guild=kwargs.get("guild"),
            message=kwargs.get("message"),
            embed_config=kwargs.get("embed_config"),
        )
        await factoid.create()

        try:
            del self.factoid_cache[self.get_cache_key(trigger, ctx.guild)]
        except KeyError:
            pass

        await util.send_confirm_embed(ctx, f"Successfully added factoid *{trigger}*")

    async def delete_factoid(self, ctx, trigger):
        factoid = await self.get_factoid_from_query(trigger, ctx.guild)
        if not factoid:
            await util.send_deny_embed(ctx, "I couldn't find that factoid")
            return

        should_delete = await self.bot.confirm(
            ctx, "This will remove the factoid forever. Are you sure?"
        )
        if not should_delete:
            return

        await factoid.delete()

    async def match(self, _, __, content):
        return content.startswith("?")

    async def response(self, config, ctx, content, _):
        if not ctx.guild:
            return

        query = content[1:].split(" ")[0]

        factoid = await self.get_factoid_from_query(query, ctx.guild)
        if not factoid:
            return

        embed = self.get_embed_from_factoid(factoid)

        content = factoid.message if not embed else None

        try:
            await util.send_with_mention(
                ctx,
                content=content,
                embed=embed,
                targets=ctx.message.mentions or [ctx.author],
            )
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "info",
                f"Sending factoid: {query} (triggered by {ctx.author} in #{ctx.channel.name})",
                send=True,
            )
        except Exception as e:
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not send factoid",
                exception=e,
            )
            await util.send_with_mention(ctx, factoid.message)

        await self.dispatch_relay_factoid(config, ctx, factoid.message)

    def message_has_mentions(self, message):
        if message.mention_everyone:
            return True
        if message.role_mentions:
            return True
        if message.mentions:
            return True
        return False

    async def dispatch_relay_factoid(self, config, ctx, message):
        relay_cog = self.bot.cogs.get("DiscordRelay")
        if not relay_cog:
            return

        # add to the relay plugin queue if it's loaded
        if not ctx.channel.id in self.bot.extension_states.get("relay", {}).get(
            "channels", []
        ):
            return

        ctx.message.content = message

        await relay_cog.response(config, ctx, message, "")

    async def load_jobs(self):
        factoids = await self.get_all_factoids()

        if not factoids:
            return

        factoid_cache = collections.defaultdict(set)
        for factoid in factoids:
            factoid_set = factoid_cache[int(factoid.guild)]
            factoid_set.add(factoid.text)
            self.configure_job(factoid)

        # remove jobs for deleted factoids
        for guild_id in factoid_cache.keys():
            for looped_factoid_key in self.loop_jobs[guild_id].keys():
                if not looped_factoid_key in factoid_cache[guild_id]:
                    del self.loop_jobs[guild_id][looped_factoid_key]

    def configure_job(self, factoid):
        guild_loop_jobs = self.loop_jobs[int(factoid.guild)]

        old_loop_config = guild_loop_jobs.get(factoid.text, {})

        if not factoid.loop_config:
            # delete stale job
            if old_loop_config:
                del guild_loop_jobs[factoid.text]
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

        guild_loop_jobs[factoid.text] = loop_config

    async def execute(self, config, guild):
        compare_time = datetime.datetime.utcnow()

        if compare_time > self.loop_cache_update_time:
            await self.load_jobs()
            self.loop_cache_update_time = (
                datetime.datetime.utcnow()
                + datetime.timedelta(minutes=self.LOOP_UPDATE_MINUTES)
            )

        for factoid_key, loop_config in self.loop_jobs.get(guild.id, {}).items():
            finish_time = loop_config.get("finish_time")
            if not finish_time or compare_time < finish_time:
                continue

            channel = None
            sleep_duration = None
            factoid = await self.get_factoid_from_query(factoid_key, guild)

            embed = self.get_embed_from_factoid(factoid)
            content = factoid.message if not embed else None

            try:
                sleep_duration = int(loop_config.get("sleep_duration"))
            except Exception:
                continue

            for channel_id in loop_config.get("channel_ids", []):
                try:
                    channel = guild.get_channel(int(channel_id))
                    # update time of next message
                    loop_config[
                        "finish_time"
                    ] = datetime.datetime.utcnow() + datetime.timedelta(
                        minutes=sleep_duration
                    )

                    await self.bot.guild_log(
                        guild,
                        "logging_channel",
                        "info",
                        f"Sending looped factoid: {factoid_key} in #{channel.name}",
                        send=True,
                    )
                    message = await channel.send(content=content, embed=embed)
                    context = await self.bot.get_context(message)
                    await self.dispatch_relay_factoid(config, context, factoid.message)
                except Exception as e:
                    await self.bot.guild_log(
                        guild,
                        "logging_channel",
                        "error",
                        f"Could not send looped factoid: {factoid_key} in #{channel.name}",
                        exception=e,
                        critical=True,
                    )

    # main clock for looping
    async def wait(self, _, __):
        await asyncio.sleep(60)

    @commands.group(
        brief="Executes a factoid command",
        description="Executes a factoid command",
    )
    async def factoid(self, ctx):
        pass

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.check(no_mentions)
    @commands.guild_only()
    @factoid.command(
        brief="Creates a factoid",
        description="Creates a custom factoid with a specified name",
        usage="[factoid-name] [factoid-output] |optional-embed-json-upload|",
    )
    async def remember(self, ctx, factoid_name: str, *, message: str):
        embed_config = await util.get_json_from_attachments(ctx.message, as_string=True)
        await self.add_factoid(
            ctx,
            trigger=factoid_name,
            channel=str(ctx.message.channel.id),
            guild=str(ctx.guild.id),
            message=message,
            embed_config=embed_config,
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Deletes a factoid",
        description="Deletes a factoid permanently, including extra config",
        usage="[factoid-name]",
    )
    async def forget(self, ctx, factoid_name: str):
        await self.delete_factoid(ctx, factoid_name)
        await util.send_confirm_embed(
            ctx, f"Successfully deleted factoid: *{factoid_name}*"
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
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
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)
        if not factoid:
            await util.send_deny_embed(ctx, "I couldn't find that factoid")
            return

        if factoid.loop_config:
            await util.send_confirm_embed(
                ctx, "Deleting previous loop configuration..."
            )

        new_loop_config = json.dumps(
            {"sleep_duration": sleep_duration, "channel_ids": channel_ids}
        )
        await factoid.update(loop_config=new_loop_config).apply()

        await util.send_confirm_embed(
            ctx, f"Successfully saved loop config for {factoid_name}"
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Removes a factoid's loop config",
        description="De-loops a pre-existing factoid",
        usage="[factoid-name]",
    )
    async def deloop(self, ctx, factoid_name: str):
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)
        if not factoid:
            await util.send_deny_embed(ctx, "I couldn't find that factoid")
            return

        if not factoid.loop_config:
            await util.send_deny_embed(ctx, "There is no loop config for that factoid")
            return

        await factoid.update(loop_config=None).apply()

        await util.send_confirm_embed(ctx, "Loop config deleted")

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Displays loop config",
        description="Retrieves and displays the loop config for a specific factoid",
        usage="[factoid-name]",
    )
    async def job(self, ctx, factoid_name: str):
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)

        if not factoid:
            await util.send_deny_embed(ctx, "I couldn't find that factoid")
            return

        if not factoid.loop_config:
            await util.send_deny_embed(ctx, "There is no loop config for that factoid")
            return

        try:
            loop_config = json.loads(factoid.loop_config)
        except Exception:
            await util.send_deny_embed(
                ctx, "I couldn't process the JSON for that loop config"
            )
            return

        embed_label = ""
        if factoid.embed_config:
            embed_label = "(embed)"

        embed = LoopEmbed(
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
            "#" + getattr(ctx.guild.get_channel(int(channel_id)), "name", "Unknown")
            for channel_id in channel_ids
        ]
        embed.add_field(name="Channels", value=", ".join(channels), inline=False)

        embed.add_field(
            name="Next execution (UTC)",
            value=self.loop_jobs.get(ctx.guild.id, {})
            .get(factoid_name, {})
            .get("finish_time", "Unknown"),  # get-er-done
        )

        await util.send_with_mention(ctx, embed=embed)

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        name="json",
        brief="Gets embed JSON",
        description="Gets embed JSON for a factoid",
        usage="[factoid-name]",
    )
    async def _json(self, ctx, factoid_name: str):
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)

        if not factoid:
            await util.send_deny_embed(ctx, "I couldn't find that factoid")
            return

        if not factoid.embed_config:
            await util.send_deny_embed(ctx, "There is no embed config for that factoid")
            return

        formatted = json.dumps(json.loads(factoid.embed_config), indent=4)
        json_file = discord.File(
            io.StringIO(formatted),
            filename=f"{factoid_name}-factoid-embed-config-{datetime.datetime.utcnow()}.json",
        )

        await util.send_with_mention(ctx, file=json_file)

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        brief="Lists loop jobs",
        description="Lists all the currently cached loop jobs",
    )
    async def jobs(self, ctx):
        all_jobs = self.loop_jobs.get(ctx.guild.id, {})

        if not all_jobs:
            await util.send_deny_embed(
                ctx,
                f"There are no currently running factoid loops (next cache update: {self.loop_cache_update_time} UTC)",
            )
            return

        embed_kwargs = {}
        for factoid_name, loop_config in all_jobs.items():
            finish_time = loop_config.get("finish_time", "???")
            embed_kwargs[factoid_name] = f"Next execution: {finish_time} UTC"

        embed = util.generate_embed_from_kwargs(
            title="Running factoid loops",
            description=f"Next cache update: {self.loop_cache_update_time} UTC",
            cls=LoopEmbed,
            **embed_kwargs,
        )

        await util.send_with_mention(ctx, embed=embed)

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        name="all",
        aliases=["lsf"],
        brief="List all factoids",
        description="Shows an embed with all the factoids",
    )
    async def all_(self, ctx):
        factoids = await self.get_all_factoids(ctx.guild, hide=True)
        if not factoids:
            await util.send_deny_embed(ctx, "No factoids found!")
            return

        output_data = []
        for factoid in factoids:
            data = {"message": factoid.message, "embed": bool(factoid.embed_config)}
            output_data.append({factoid.text: data})

        yaml_file = discord.File(
            io.StringIO(yaml.dump(output_data)),
            filename=f"factoids-for-server-{ctx.guild.id}-{datetime.datetime.utcnow()}.yaml",
        )

        await ctx.send(file=yaml_file)

    @util.with_typing
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    @factoid.command(
        brief="Hides a factoid",
        description="Hides a factoid from showing in the all response",
        usage="[factoid-name]",
    )
    async def hide(
        self,
        ctx,
        factoid_name: str,
    ):
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)
        if not factoid:
            await util.send_deny_embed(ctx, "I couldn't find that factoid")
            return

        if factoid.hidden:
            await util.send_deny_embed(ctx, "That factoid is already hidden")
            return

        await factoid.update(hidden=True).apply()

        await util.send_confirm_embed(ctx, "That factoid is now hidden")

    @util.with_typing
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    @factoid.command(
        brief="Unhides a factoid",
        description="Unhides a factoid from showing in the all response",
        usage="[factoid-name]",
    )
    async def unhide(
        self,
        ctx,
        factoid_name: str,
    ):
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)
        if not factoid:
            await util.send_deny_embed(ctx, "I couldn't find that factoid")
            return

        if not factoid.hidden:
            await util.send_deny_embed(ctx, "That factoid is already unhidden")
            return

        await factoid.update(hidden=False).apply()

        await util.send_confirm_embed(ctx, "That factoid is now unhidden")
