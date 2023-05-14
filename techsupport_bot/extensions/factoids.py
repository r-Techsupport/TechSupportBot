"""
This extension manages everything needed for the factoid command and all factoid calls(EG: ?factoid)
"""
import asyncio
import datetime
import io
import json
import uuid

import aiocron
import base
import discord
import expiringdict
import munch
import util
import yaml
from discord.ext import commands


async def setup(bot):
    """
    define database tables, register in config, as a cog, and a extension
    """

    class Factoid(bot.db.Model):
        """define the factoid class for the table"""

        __tablename__ = "factoids"

        factoid_id = bot.db.Column(bot.db.Integer, primary_key=True)
        text = bot.db.Column(bot.db.String)
        guild = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        embed_config = bot.db.Column(bot.db.String, default=None)
        hidden = bot.db.Column(bot.db.Boolean, default=False)

    class FactoidCron(bot.db.Model):
        """define the factoid scheduler."""

        __tablename__ = "factoid_cron"

        job_id = bot.db.Column(bot.db.Integer, primary_key=True)
        factoid = bot.db.Column(
            bot.db.Integer, bot.db.ForeignKey("factoids.factoid_id")
        )
        channel = bot.db.Column(bot.db.String)
        cron = bot.db.Column(bot.db.String)

    class FactoidResponseEvent(bot.db.Model):
        """Define the factoid response event"""

        __tablename__ = "factoid_responses"

        event_id = bot.db.Column(bot.db.Integer, primary_key=True)
        ref_content = bot.db.Column(bot.db.String)
        text = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        embed_config = bot.db.Column(bot.db.String, default=None)
        channel_name = bot.db.Column(bot.db.String)
        server_name = bot.db.Column(bot.db.String)
        responder = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    # dealing with the config.yml file located in ../
    config = bot.ExtensionConfig()
    config.add(
        key="manage_roles",
        datatype="list",
        title="Manage factoids roles",
        description="The roles required to manage factoids",
        default=["Factoids"],
    )
    config.add(
        key="response_listen_channels",
        datatype="list",
        title="Factoids response listen channels",
        description="The list of channel ID's to listen for factoid response events",
        default=[],
    )
    config.add(
        key="linx_url",
        datatype="str",
        title="Linx API URL",
        description="The URL to an optional Linx (github.com/andreimarcu/linx-server) \
            API for pastebinning factoid-all responses",
        default=None,
    )

    await bot.add_cog(
        FactoidManager(
            bot=bot,
            models=[Factoid, FactoidCron, FactoidResponseEvent],
            extension_name="factoids",
        )
    )
    bot.add_extension_config("factoids", config)


async def has_manage_factoids_role(ctx):
    """
    see if the user that queried has the perms to manage roles
    """
    config = await ctx.bot.get_context_config(ctx)
    factoid_roles = []
    for name in config.extensions.factoids.manage_roles.value:
        factoid_role = discord.utils.get(ctx.guild.roles, name=name)
        if not factoid_role:
            continue
        factoid_roles.append(factoid_role)

    if not factoid_roles:
        raise commands.CommandError("no factoid management roles found")
    # Checking against the user to see if they have the roles specified in the config
    if not any(
        factoid_role in getattr(ctx.author, "roles", [])
        for factoid_role in factoid_roles
    ):
        raise commands.MissingAnyRole(factoid_roles)

    return True


async def no_mentions(ctx):
    """
    ensure the remembered factoid does not contain any mass pings
    """
    if (
        ctx.message.mention_everyone
        or ctx.message.role_mentions
        or ctx.message.mentions
        or ctx.message.channel_mentions
    ):
        await ctx.send_deny_embed(
            "I cannot remember factoids with user/role/channel mentions"
        )
        return False
    return True


class LoopEmbed(discord.Embed):
    """define the class to loop the embed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.blurple()


class FactoidManager(base.MatchCog):
    """
    delete, remember, fetch, and listen for factoid calls
    """

    LOOP_UPDATE_MINUTES = 10

    async def preconfig(self):
        """define the preconfig of the factoid itself"""
        self.factoid_cache = expiringdict.ExpiringDict(
            max_len=100, max_age_seconds=1200
        )
        # set a hard time limit on repeated cronjob DB calls
        self.cronjob_cache = expiringdict.ExpiringDict(max_len=100, max_age_seconds=300)
        await self.bot.logger.info("Loading factoid jobs", send=True)
        await self.kickoff_jobs()

    async def get_all_factoids(self, guild=None, hide=False):
        """Method to get all the factoids from a command."""
        if guild and not hide:
            factoids = await self.models.Factoid.query.where(
                self.models.Factoid.guild == str(guild.id)
            ).gino.all()
        elif guild and hide:
            factoids = (
                await self.models.Factoid.query.where(
                    self.models.Factoid.guild == str(guild.id)
                )
                # hiding hidden factoids
                .where(self.models.Factoid.hidden == False).gino.all()
            )
        else:
            factoids = await self.bot.db.all(self.models.Factoid.query)

        if factoids:
            factoids.sort(key=lambda factoid: factoid.text)

        return factoids

    def get_cache_key(self, query, guild):
        """Method to get the cache key from the guild."""
        return f"{guild.id}_{query}"

    async def get_factoid_from_query(self, query, guild):
        """
        search db for factoid, including flag (EG: ?help)
        """
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
        """Method to turn the json into an embed for discord."""
        if not factoid.embed_config:
            return None

        embed_config = json.loads(factoid.embed_config)

        return discord.Embed.from_dict(embed_config)

    async def add_factoid(self, ctx, **kwargs):
        """Method to add a factoid."""
        trigger = kwargs.get("trigger")

        # first check if key already exists
        factoid = await self.get_factoid_from_query(trigger, ctx.guild)
        if factoid:
            # delete old one
            should_delete = await ctx.confirm(
                "This factoid already exists. Should I overwrite it?"
            )
            if not should_delete:
                return
            await factoid.delete()

        # finally, add new entry
        factoid = self.models.Factoid(
            text=trigger,
            guild=kwargs.get("guild"),
            message=kwargs.get("message"),
            embed_config=kwargs.get("embed_config"),
        )
        await factoid.create()

        try:
            del self.factoid_cache[self.get_cache_key(trigger, ctx.guild)]
            # if it can't find where it is, then don't continue
        except KeyError:
            pass

        await ctx.send_confirm_embed(f"Successfully added factoid *{trigger}*")

    async def delete_factoid(self, ctx, trigger):
        """Method to delete a factoid."""
        factoid = await self.get_factoid_from_query(trigger, ctx.guild)
        if not factoid:
            await ctx.send_deny_embed("I couldn't find that factoid")
            return

        should_delete = await ctx.confirm(
            "This will remove the factoid forever. Are you sure?"
        )
        if not should_delete:
            return

        await factoid.delete()

    async def match(self, _, __, content):
        """Method to match the factoid with the correct start."""
        return content.startswith("?")

    async def response(self, config, ctx, content, _):
        """Method to give a response once a factoid is called (or attempted)."""
        if not ctx.guild:
            return
        # copy the arguments starting with index one, and reference the first argument
        # Replaces \n with spaces so factoid can be called even with newlines
        query = content[1:].replace("\n", " ").split(" ")[0]
        factoid = await self.get_factoid_from_query(query, ctx.guild)
        if not factoid:
            return

        embed = self.get_embed_from_factoid(factoid)
        # if the json doesn't include non embed argument, then don't send anything
        # otherwise send message text with embed
        content = factoid.message if not embed else None

        try:
            # define the message and send it
            message = await ctx.send(
                content=content,
                embed=embed,
                # if nobody pinged, ping the author, if mentioned, ping the author and the mention
                targets=ctx.message.mentions or [ctx.author],
            )
            # log it  in the logging channel with type info and generic content
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "info",
                f"Sending factoid: {query} (triggered by {ctx.author} in #{ctx.channel.name})",
                send=True,
            )
            # if something breaks, also log it
        except Exception as e:
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not send factoid",
                exception=e,
            )
            # finally, send the message
            message = await ctx.send(factoid.message)

        self.dispatch(ctx.author, message, factoid)

        if ctx.message.mentions or ctx.message.reference:
            await self.process_response_event(ctx, factoid)

    async def process_response_event(self, ctx, factoid):
        """Method to process how the response should be sent to users."""
        config = await self.bot.get_context_config(ctx)
        if (
            not str(ctx.channel.id)
            in config.extensions.factoids.response_listen_channels.value
        ):
            return
        # how many users are found to reference in the response
        found = 0
        # make sure the users are not a bot
        users = {}
        for user in ctx.message.mentions:
            if user.bot:
                continue
            if user.id == ctx.author.id:
                continue
            users[user] = None
        # if the message has a ping, and the ping is *not* the author,
        # add 1 to the found count and add the user to the list of users referenced
        if (
            ctx.message.reference
            and ctx.message.reference.cached_message
            and ctx.message.reference.cached_message.author.id != ctx.author.id
        ):
            users[
                ctx.message.reference.cached_message.author
            ] = ctx.message.reference.cached_message
            found += 1
        # looking for up to 100 users to mention
        async for message in ctx.channel.history(limit=100):
            # if it thinks it found a user but *not* in the users dict, don't even continue looking
            if found >= len(users):
                break
            # if the author is already in the list of users, then don't add them
            if not message.author in users:
                continue

            saved_message = users.get(message.author)
            if saved_message:
                continue
            # adding the author to the list of messages
            users[message.author] = message
            found += 1
        # logging that the above was done
        await self.bot.guild_log(
            ctx.guild,
            "logging_channel",
            "info",
            "Processing factoid response event",
            send=True,
        )
        # more logging
        for user, message in users.items():
            event = self.models.FactoidResponseEvent(
                ref_content=message.content,
                text=factoid.text,
                message=factoid.message,
                embed_config=factoid.embed_config,
                channel_name=ctx.channel.name,
                server_name=ctx.guild.name,
                responder=str(ctx.author),
            )
            await event.create()

    def dispatch(self, author, message, factoid):
        """Self dispatch the bot for a factoid event."""
        self.bot.dispatch(
            "factoid_event",
            munch.Munch(author=author, message=message, factoid=factoid),
        )

    async def kickoff_jobs(self):
        """
        get a list of all cronjobs and start them
        """
        jobs = await self.models.FactoidCron.query.gino.all()
        for job in jobs:
            asyncio.create_task(self.cronjob(job))

    async def cronjob(self, job):
        """Run a cron job for a factoid."""
        runtime_id = uuid.uuid4()
        self.cronjob_cache[runtime_id] = job
        job_id = job.job_id

        while True:
            job = self.cronjob_cache.get(runtime_id)
            if not job:
                from_db = await self.models.FactoidCron.query.where(
                    self.models.FactoidCron.job_id == job_id
                ).gino.first()
                if not from_db:
                    # this factoid job has been deleted from the DB
                    # TODO: log this event
                    return
                job = from_db
                self.cronjob_cache[runtime_id] = job

            # TODO: pass exception to guild log interface
            try:
                await aiocron.crontab(job.cron).next()
            except Exception as e:
                await self.bot.logger.error(
                    "Could not await cron completion", exception=e
                )
                await asyncio.sleep(300)

            factoid = await self.models.Factoid.query.where(
                self.models.Factoid.factoid_id == job.factoid
            ).gino.first()
            if not factoid:
                await self.bot.logger.warning(
                    "Could not find factoid referenced by job - will retry after waiting"
                )
                continue

            # get_embed accepts job as a factoid object
            embed = self.get_embed_from_factoid(factoid)
            content = factoid.message if not embed else None

            channel = self.bot.get_channel(int(job.channel))
            if not channel:
                await self.bot.logger.warning(
                    "Could not find channel to send factoid cronjob - will retry after waiting"
                )
                continue

            message = await channel.send(content=content, embed=embed)
            self.dispatch(channel.guild.get_member(self.bot.user.id), message, factoid)

    @commands.group(
        brief="Executes a factoid command",
        description="Executes a factoid command",
    )
    async def factoid(self, ctx):
        """Method to make the command for the factoid."""

        # Executed if there are no/invalid args supplied
        await base.extension_help(self, ctx, self.__module__[11:])

        print(f"Factoid command called in channel {ctx.channel}")

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.check(no_mentions)
    @commands.guild_only()
    # updating the description for this command
    @factoid.command(
        brief="Creates a factoid",
        description="Creates a custom factoid with a specified name",
        usage="[factoid-name] [factoid-output] |optional-embed-json-upload|",
    )
    async def remember(self, ctx, factoid_name: str, *, message: str):
        """Method to remember factoid."""
        embed_config = await util.get_json_from_attachments(ctx.message, as_string=True)
        await self.add_factoid(
            ctx,
            trigger=factoid_name,
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
        """Method to forget a factoid."""
        await self.delete_factoid(ctx, factoid_name)
        await ctx.send_confirm_embed(f"Successfully deleted factoid: *{factoid_name}*")

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
        """Method to handle the json for the factoid creation."""
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)

        if not factoid:
            await ctx.send_deny_embed("I couldn't find that factoid")
            return

        if not factoid.embed_config:
            await ctx.send_deny_embed("There is no embed config for that factoid")
            return

        formatted = json.dumps(json.loads(factoid.embed_config), indent=4)
        json_file = discord.File(
            io.StringIO(formatted),
            filename=f"{factoid_name}-factoid-embed-config-{datetime.datetime.utcnow()}.json",
        )

        await ctx.send(file=json_file)

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Loops a factoid",
        description="Loops a pre-existing factoid",
        usage="[factoid-name] [cron_config] [channel]",
    )
    async def loop(
        self,
        ctx,
        factoid_name: str,
        cron_config: str,
        channel: discord.TextChannel,
    ):
        """Method to define how the loop of a factoid will work."""
        # check if loop already exists
        job = (
            await self.models.FactoidCron.join(self.models.Factoid)
            .select()
            .where(self.models.FactoidCron.channel == str(channel.id))
            .where(self.models.Factoid.text == factoid_name)
            .gino.first()
        )
        if job:
            await ctx.send_deny_embed("That factoid is already looping in this channel")
            return

        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)
        if not factoid:
            await ctx.send_deny_embed("That factoid does not exist")
            return

        # TODO: validate cron before passing to DB
        job = self.models.FactoidCron(
            factoid=factoid.factoid_id, channel=str(channel.id), cron=cron_config
        )
        await job.create()

        asyncio.create_task(self.cronjob(job))

        await ctx.send_confirm_embed("Factoid loop created")

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Removes a factoid's loop config",
        description="De-loops a pre-existing factoid",
        usage="[factoid-name] [channel]",
    )
    async def deloop(self, ctx, factoid_name: str, channel: discord.TextChannel):
        """Method to deloop the loop that was created."""
        job = (
            await self.models.FactoidCron.query.where(
                self.models.FactoidCron.channel == str(channel.id)
            )
            .where(self.models.Factoid.text == factoid_name)
            .gino.first()
        )
        if not job:
            await ctx.send_deny_embed("That job does not exist")
            return

        await job.delete()

        await ctx.send_confirm_embed(
            "Loop job deleted (please wait some time to see changes)"
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Displays loop config",
        description="Retrieves and displays the loop config for a specific factoid",
        usage="[factoid-name] [channel]",
    )
    async def job(self, ctx, factoid_name: str, channel: discord.TextChannel):
        """Method to check if a looping job already exists."""
        job = (
            await self.models.FactoidCron.join(self.models.Factoid)
            .select()
            .where(self.models.FactoidCron.channel == str(channel.id))
            .where(self.models.Factoid.text == factoid_name)
            .gino.first()
        )
        if not job:
            await ctx.send_deny_embed("That job does not exist")
            return

        embed_label = ""
        if job.embed_config:
            embed_label = "(embed)"

        embed = LoopEmbed(
            title=f"Loop config for {factoid_name} {embed_label}",
            description=f'"{job.message}"',
        )

        embed.add_field(name="Channel", value=f"#{channel.name}")
        embed.add_field(name="Cron config", value=job.cron)

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        brief="Lists loop jobs",
        description="Lists all the currently registered loop jobs",
    )
    async def jobs(self, ctx):
        """Method to pull up the loop jobs."""
        jobs = (
            await self.models.FactoidCron.join(self.models.Factoid)
            .select()
            .where(self.models.Factoid.guild == str(ctx.guild.id))
            .gino.all()
        )
        if not jobs:
            await ctx.send_deny_embed(
                "There are no registered factoid loop jobs for this guild"
            )
            return

        embed = LoopEmbed(title=f"Factoid loop jobs for {ctx.guild.name}")
        for job in jobs[:10]:
            channel = self.bot.get_channel(int(job.channel))
            if not channel:
                continue
            embed.add_field(
                name=f"{job.text} - #{channel.name}", value=job.cron, inline=False
            )

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        name="all",
        aliases=["lsf"],
        brief="List all factoids",
        description="Shows an embed with all the factoids",
    )
    async def all_(self, ctx, flag=None):
        """Method to pull up all the factoids."""
        factoids = await self.get_all_factoids(ctx.guild, hide=True)
        if not factoids:
            await ctx.send_deny_embed("No factoids found!")
            return

        flag = flag.lower() if flag else flag
        config = await self.bot.get_context_config(ctx)
        if flag == "file" or not config.extensions.factoids.linx_url.value:
            await self.send_factoids_as_file(ctx, factoids)
            return

        try:
            html = await self.generate_html(ctx, factoids)
            headers = {
                "Content-Type": "text/plain",
            }
            response = await self.bot.http_call(
                "put",
                config.extensions.factoids.linx_url.value,
                headers=headers,
                data=io.StringIO(html),
                get_raw_response=True,
            )
            url = await response.text()
            filename = url.split("/")[-1]
            url = url.replace(filename, f"selif/{filename}")
            await ctx.send_confirm_embed(url)
        except Exception as e:
            await self.send_factoids_as_file(ctx, factoids)
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not render/send all-factoid HTML",
                exception=e,
            )

    async def generate_html(self, ctx, factoids):
        """Method to generate a link for html in a factoid."""
        list_items = ""
        for factoid in factoids:
            embed_text = " (embed)" if factoid.embed_config else ""
            list_items += (
                f"<li><code>{factoid.text}{embed_text} - {factoid.message}</code></li>"
            )
        body_contents = f"<ul>{list_items}</ul>"
        output = f"""
        <!DOCTYPE html>
        <html>
        <body>
        <h3>Factoids for {ctx.guild.name}</h3>
        {body_contents}
        </body>
        </html>
        """
        return output

    async def send_factoids_as_file(self, ctx, factoids):
        """Method to send all the factoids as a file."""
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
        """Method to hide the factoid from the 'all' list."""
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)
        if not factoid:
            await ctx.send_deny_embed("I couldn't find that factoid")
            return

        if factoid.hidden:
            await ctx.send_deny_embed("That factoid is already hidden")
            return

        await factoid.update(hidden=True).apply()

        await ctx.send_confirm_embed("That factoid is now hidden")

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
        """Method to unhide the factoid that you have hidden."""
        factoid = await self.get_factoid_from_query(factoid_name, ctx.guild)
        if not factoid:
            await ctx.send_deny_embed("I couldn't find that factoid")
            return

        if not factoid.hidden:
            await ctx.send_deny_embed("That factoid is already unhidden")
            return

        await factoid.update(hidden=False).apply()

        await ctx.send_confirm_embed("That factoid is now unhidden")
