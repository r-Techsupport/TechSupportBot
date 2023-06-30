"""
Name: Factoids
Info: Makes callable slices of text
Unit tests: No
Config: manage_roles, response_listen_channels, linx_url, prefix
API: None
Databases: Postgres
Models: Factoid, FactoidJob
Subcommands: remember, forget, info, json, all, search, loop, deloop, job, jobs, hide, unhide,
             alias, dealias
Defines: # TODO pretty up aobve
"""
import asyncio
import datetime
import io
import json
import re
from socket import gaierror

import aiocron
import base
import discord
import expiringdict
import munch
import ui
import util
import yaml
from aiohttp.client_exceptions import InvalidURL
from base import auxiliary
from discord.ext import commands
from error import FactoidNotFoundError, TooLongFactoidMessageError


async def setup(bot):
    """
    define database tables, register in config, as a cog, and a extension
    """

    class Factoid(bot.db.Model):
        """define the factoid class for the table"""

        __tablename__ = "factoids"

        factoid_id = bot.db.Column(bot.db.Integer, primary_key=True)
        name = bot.db.Column(bot.db.String)
        guild = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        embed_config = bot.db.Column(bot.db.String, default=None)
        hidden = bot.db.Column(bot.db.Boolean, default=False)
        alias = bot.db.Column(bot.db.String, default=None)

    class FactoidJob(bot.db.Model):
        """define the factoid scheduler."""

        __tablename__ = "factoid_jobs"

        job_id = bot.db.Column(bot.db.Integer, primary_key=True)
        factoid = bot.db.Column(
            bot.db.Integer, bot.db.ForeignKey("factoids.factoid_id")
        )
        channel = bot.db.Column(bot.db.String)
        cron = bot.db.Column(bot.db.String)

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
        description="The URL to an optional Linx API for pastebinning factoid-all responses",
        default=None,
    )
    config.add(
        key="prefix",
        datatype="str",
        title="Factoid prefix",
        description="Prefix for calling factoids",
        default="?",
    )

    await bot.add_cog(
        FactoidManager(
            bot=bot,
            models=[Factoid, FactoidJob],
            extension_name="factoids",
        )
    )
    bot.add_extension_config("factoids", config)


async def has_manage_factoids_role(ctx: commands.Context):
    """-COMMAND CHECK-
    Checks if the invoker has a factoid management role

    Args:
        ctx (commands.Context): Context used for getting the config file

    Raises:
        commands.CommandError: No management roles assigned in the config
        commands.MissingAnyRole: Invoker doesn't have a factoid management role

    Returns:
        bool: Whether the invoker has a factoid management role
    """
    config = await ctx.bot.get_context_config(ctx)
    factoid_roles = []
    # Gets permitted roles
    for name in config.extensions.factoids.manage_roles.value:
        factoid_role = discord.utils.get(ctx.guild.roles, name=name)
        if not factoid_role:
            continue
        factoid_roles.append(factoid_role)

    if not factoid_roles:
        raise commands.CommandError(
            "No factoid management roles found in the config file"
        )
    # Checking against the user to see if they have the roles specified in the config
    if not any(
        factoid_role in getattr(ctx.author, "roles", [])
        for factoid_role in factoid_roles
    ):
        raise commands.MissingAnyRole(factoid_roles)

    return True


async def no_mentions(ctx: commands.Context):
    """-COMMAND CHECK-
    Makes sure a message doesn't contain mass mentions

    Args:
        ctx (commands.Context): Context to send a deny message to

    Returns:
        bool: Whether the message contains mass mentions or not
    """

    if (
        ctx.message.mention_everyone  # @everyone
        or ctx.message.role_mentions  # @role
        or ctx.message.mentions  # @person
        or ctx.message.channel_mentions  # #Channel
    ):
        await auxiliary.send_deny_embed(
            "I cannot remember factoids with user/role/channel mentions",
            channel=ctx.channel,
        )
        return False
    return True


class FactoidManager(base.MatchCog):
    """
    Delete, remember, fetch, and listen for factoid calls
    """

    LOOP_UPDATE_MINUTES = 10

    async def preconfig(self):
        """Preconfig for factoid jobs"""
        self.factoid_cache = expiringdict.ExpiringDict(
            max_len=100, max_age_seconds=1200
        )
        # set a hard time limit on repeated cronjob DB calls
        self.cronjob_cache = expiringdict.ExpiringDict(max_len=100, max_age_seconds=300)
        self.factoid_all_cache = expiringdict.ExpiringDict(
            max_len=1, max_age_seconds=600
        )
        self.active_jobs = []
        await self.bot.logger.info("Loading factoid jobs", send=True)
        await self.kickoff_jobs()

    # -- DB calls --
    async def delete_factoid_call(self, factoid):
        """Calls the db to delete a factoid

        Args:
            factoid (Factoid): The factoid to delete
        """
        # Removes the `factoid all` cache since it has become outdated
        if self.factoid_all_cache:
            self.factoid_all_cache.pop(0)

        # Deloops the factoid first (if it's looped)
        jobs = (
            await self.models.FactoidJob.query.where(
                self.models.Factoid.guild == factoid.guild
            )
            .where(self.models.Factoid.factoid_id == factoid.factoid_id)
            .gino.all()
        )
        if jobs:
            for job in jobs:
                await job.delete()

        await factoid.delete()

    async def create_factoid_call(
        self,
        factoid_name: str,
        guild: str,
        message: str,
        embed_config: str,
        alias: str = None,
    ):
        """Calls the DB to create a factoid

        Args:
            factoid_name (str): The name of the factoid
            guild (str): Guild of the factoid
            message (str): Message the factoid should send
            embed_config (str): Whether the factoid has an embed set up
            alias (str, optional): The parent factoid. Defaults to None.
        """
        if len(message) > 2000:
            raise TooLongFactoidMessageError

        # Removes the `factoid all` cache since it has become outdated
        if self.factoid_all_cache:
            self.factoid_all_cache.pop(0)

        factoid = self.models.Factoid(
            name=factoid_name.lower(),
            guild=guild,
            message=message,
            embed_config=embed_config,
            alias=alias,
        )
        await factoid.create()

    async def modify_factoid_call(
        self,
        factoid,
        factoid_name: str = None,
        message: str = None,
        embed_config: str = None,
        hidden: bool = None,
        alias: str = None,
    ):
        """Makes a DB call to modify a factoid

        Args:
            factoid (Factoid): Factoid to modify.
            factoid_name (str, optional): New factoid name. Defaults to None.
            message (str, optional): New factoid message. Defaults to None.
            embed_config (str, optional): Whether the factoid has an embed set up. Defaults to None.
            hidden (bool, optional): Whether the factoid is hidden. Defaults to None.
            alias (str, optional): New parent factoid. Defaults to None.
        """
        if message and len(message) > 2000:
            raise TooLongFactoidMessageError

        # Removes the `factoid all` cache since it has become outdated
        if self.factoid_all_cache:
            self.factoid_all_cache.pop(0)

        await factoid.update(
            name=factoid_name.lower() if factoid_name is not None else factoid.name,
            message=message if message is not None else factoid.message,
            embed_config=embed_config
            if embed_config is not None
            else factoid.embed_config,
            hidden=hidden if hidden is not None else factoid.hidden,
            alias=alias if alias is not None else None,
        ).apply()

    # -- Utility --
    async def confirm_factoid_deletion(
        self, factoid_name: str, ctx: commands.Context
    ) -> bool:
        """Confirms if a factoid should be deleted

        Args:
            factoid_name (str): The factoid that is being prompted for deletion
            ctx (commands.Context): Used to return the message"""

        view = ui.Confirm()
        await view.send(
            message=f"The factoid `{factoid_name.lower()}` already exists. Should I overwrite it?",
            channel=ctx.channel,
            author=ctx.author,
        )

        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return False
        if view.value is ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                message=f"The factoid `{factoid_name.lower()}` was not removed.",
                channel=ctx.channel,
            )
            return False

        return True

    async def handle_parent_change(
        self, ctx: commands.Context, aliases: list, new_name: str
    ):
        """Changes the list of aliases to point to a new name

        Args:
            aliases (list): A list of aliases to change
            new_name (str): The name of the new parent
            ctx (commands.Context): Used for cache handling
        """

        for alias in aliases:
            # Doesn't handle the initial, changed alias
            if alias.name == new_name:
                continue
            # Updates the existing aliases to point to the new parent
            await self.modify_factoid_call(factoid=alias, alias=new_name)
            await self.handle_cache(str(ctx.guild.id), alias.name)

    async def check_alias_recursion(
        self,
        channel: discord.TextChannel,
        guild: str,
        factoid_name: str,
        alias_name: str,
    ) -> bool:
        """Makes sure an alias isn't already present in a factoids alias list

        Args:
            channel (discord.TextChannel): The channel to send the return message to
            guild (str): The id of the guild from which the command was executed
            factoid_name (str): The name of the parent
            alias_name (str): The alias to check

        Returns:
            bool: Whether the alias recurses
        """

        # Get list of aliases of the target factoid
        factoid_aliases = (
            await self.models.Factoid.query.where(
                self.models.Factoid.alias == alias_name
            )
            .where(self.models.Factoid.guild == guild)
            .gino.all()
        )

        # Returns a True if the alias name is the same (.factoid alias a a)
        # or if the target has the alias already (.factoid alias b a, where b has a set already)
        if factoid_name == alias_name or factoid_name in [
            alias.name for alias in factoid_aliases
        ]:
            await auxiliary.send_deny_embed(
                "Can't set an alias for itself!", channel=channel
            )
            return True

        return False

    def get_embed_from_factoid(self, factoid) -> discord.Embed:
        """Gets the factoid embed from its message.

        Args:
            (Factoid) factoid: The factoid to get the json of

        Returns:
            discord.Embed: The embed of the factoid
        """
        if not factoid.embed_config:
            return None

        embed_config = json.loads(factoid.embed_config)

        return discord.Embed.from_dict(embed_config)

    async def check_lsf_cache(self, flag: str):
        """Checks whether the factoid all cache exists and is usable

        Args:
            flag (str): Used to check if previous instance was hidden

        Returns:
            str or list: The usable cache entry
        """
        if self.factoid_all_cache:
            cache = self.factoid_all_cache[0]

            # Disregards cache if the hidden flag doesn't match
            if (
                "hidden" in flag
                and not "hidden" in cache["flags"]
                or "hidden" not in flag
                and "hidden" in cache["flags"]
            ):
                self.factoid_all_cache.pop(0)  # Deletes old cache
                return None

            for value in cache:
                if value == "file" and "file" in flag:
                    yaml_file = discord.File(
                        io.StringIO(cache["file"][0]),
                        filename=cache["file"][1],
                    )
                    return yaml_file

                if value == "url" and "file" not in flag:
                    return cache["url"]

    # -- Cache functions --
    async def handle_cache(self, guild: str, factoid_name: str):
        """Deletes factoid from cache

        Args:
            guild (str): The guild to get the cache key
            factoid_name (str): The name of the factoid to remove from the cache
        """
        try:
            del self.factoid_cache[self.get_cache_key(guild, factoid_name)]
        except KeyError:  # If it can't find the factoid in the cache
            pass

    def get_cache_key(self, guild: str, factoid_name: str) -> str:
        """Gets the cache key for a guild

        Args:
            guild (str): The ID of the guild
            factoid_name (str): The name of the factoid

        Returns:
            str: The cache key
        """
        return f"{guild}_{factoid_name}"

    # -- Getting factoids --
    async def get_all_factoids(
        self, guild: str = None, list_hidden: bool = False
    ) -> list:
        """Gets all factoids from a guild

        Args:
            guild (str, optional): The guild to get the factoids from. Defaults to None.
            list_hidden (bool, optional): Whether to list hidden factoids as well.
                                          Defaults to False.

        Returns:
            list: List of factoids
        """
        # Gets factoids for a guild, including those that are hidden
        if guild and list_hidden:
            factoids = await self.models.Factoid.query.where(
                self.models.Factoid.guild == guild
            ).gino.all()
        # Gets factoids for a guild excluding the hidden ones
        elif guild and not list_hidden:
            factoids = (
                await self.models.Factoid.query.where(
                    self.models.Factoid.guild == guild
                )
                # Hides hidden factoids
                .where(self.models.Factoid.hidden is False).gino.all()
            )
        # Gets ALL factoids for ALL guilds
        else:
            factoids = await self.bot.db.all(self.models.Factoid.query)

        # Sorts them alphabetically
        if factoids:
            factoids.sort(key=lambda factoid: factoid.name)

        return factoids

    async def get_factoid_entry(self, factoid_name: str, guild: str):
        """Searches the db for a factoid by its name

        Args:
            factoid_name (str): The name of the factoid to get
            guild (str): The id of the guild for the factoid

        Returns:
            Factoid: The factoid
        """
        cache_key = self.get_cache_key(guild, factoid_name)
        factoid = self.factoid_cache.get(cache_key)
        # If the factoid isn't cached
        if not factoid:
            factoid = (
                await self.models.Factoid.query.where(
                    self.models.Factoid.name == factoid_name
                )
                .where(self.models.Factoid.guild == guild)
                .gino.first()
            )
            # Caches it
            self.factoid_cache[cache_key] = factoid

        return factoid

    async def get_factoid_or_alias(self, factoid_name: str, guild: str):
        """Gets the factoid from the DB, follows aliases

        Args:
            factoid_name (str): The name of the factoid to get
            guild (str): The id of the guild for the factoid

        Raises:
            FactoidNotFoundError: If the factoid wasn't found

        Returns:
            Factoid: The factoid
        """
        factoid = await self.get_factoid_entry(factoid_name, guild)

        if not factoid:
            raise FactoidNotFoundError(factoid=factoid_name)

        # Handling if the call is an alias
        if factoid and factoid.alias not in ["", None]:
            factoid = await self.get_factoid_entry(factoid.alias, guild)
            factoid_name = factoid.name

        return factoid

    # -- Adding and removing factoids --

    async def add_factoid(
        self,
        ctx: commands.Context,
        factoid_name: str,
        guild: str,
        message: str,
        embed_config: str,
        alias: str = None,
    ):
        """Adds a factoid with confirmation, modifies it if it already exists

        Args:
            ctx (commands.Context): The context used for the confirmation message
            factoid_name (str): The name of the factoid
            guild (str): The guild of the factoid
            message (str): The message of the factoid
            embed_config (str): The embed config of the factoid
            alias (str, optional): The parent of the factoid. Defaults to None.
        """
        fmt = "added"  # Changes to modified, used for the returned message
        name = factoid_name  # Name if the factoid doesn't exist

        # Checks if the factoid exists already
        try:
            factoid = await self.get_factoid_or_alias(factoid_name, guild)
            name = factoid.name  # Name of the parent

        except FactoidNotFoundError:
            # Adds the factoid if it doesn't exist already
            await self.create_factoid_call(
                factoid_name=name,
                guild=guild,
                message=message,
                embed_config=embed_config,
                alias=alias,
            )

        else:
            # Modifies it if it already exists

            # Confirms modification
            if await self.confirm_factoid_deletion(factoid.name, ctx) is False:
                return

            # Modifies the old entry
            fmt = "modified"
            await self.modify_factoid_call(
                factoid=await self.get_factoid_entry(factoid_name, str(ctx.guild.id)),
                factoid_name=name,
                message=message,
                embed_config=embed_config,
                alias=alias,
            )

        # Removes the factoid from the cache
        await self.handle_cache(guild, name)

        await auxiliary.send_confirm_embed(
            f"Successfully {fmt} factoid `{name.lower()}`", channel=ctx.channel
        )

    async def delete_factoid(self, ctx: commands.Context, factoid_name: str):
        """Deletes a factoid with confirmation

        Args:
            ctx (commands.Context): Context to send the confirmation message to
            factoid_name (str): Name of the factoid to remove
        """
        factoid = await self.get_factoid_or_alias(factoid_name, str(ctx.guild.id))

        # Don't confirm if this is an alias, only the parent needs confirmation
        if factoid.alias != factoid_name:
            view = ui.Confirm()
            await view.send(
                message=f"This will remove the factoid `{factoid_name.lower()}` forever."
                + " Are you sure?",
                channel=ctx.channel,
                author=ctx.author,
            )

            await view.wait()
            if view.value is ui.ConfirmResponse.TIMEOUT:
                return
            if view.value is ui.ConfirmResponse.DENIED:
                await auxiliary.send_deny_embed(
                    message=f"Factoid `{factoid_name.lower()}` was not deleted",
                    channel=ctx.channel,
                )
                return False

        await self.delete_factoid_call(factoid)
        await self.handle_cache(str(ctx.guild.id), factoid_name)

        # Don't send the confirmation message if this is an alias either
        await auxiliary.send_confirm_embed(
            f"Successfully deleted the factoid `{factoid_name.lower()}`",
            channel=ctx.channel,
        )

    # -- Getting and responding with a factoid --
    async def match(self, config, _: commands.Context, message_contents: str) -> bool:
        """Checks if a message started with the prefix from the config

        Args:
            config (Config): The config to get the prefix from
            _ (commands.Context): Ctx, not used
            message_contents (str): The message to check

        Returns:
            bool: Whether the message starts with the prefix or not
        """
        return message_contents.startswith(config.extensions.factoids.prefix.value)

    async def response(self, config, ctx: commands.Context, message_content: str, _):
        """Responds to a factoid call

        Args:
            config (Config): The server config
            ctx (commands.Context): Context of the call
            message_content (str): Content of the call
            _ (bool): Result, unused

        Raises:
            FactoidNotFoundError: Raised if a broken alias is present in the DB
        """
        if not ctx.guild:
            return
        # Checks if the first word of the content after the prefix is a valid factoid
        # Replaces \n with spaces so factoid can be called even with newlines
        query = message_content[1:].replace("\n", " ").split(" ")[0].lower()
        factoid = await self.get_factoid_entry(query, str(ctx.guild.id))
        if not factoid:
            await self.logger.debug(f"Invalid factoid call {query} from {ctx.guild.id}")
            return

        # If the factoid is an alias
        if factoid.alias not in ["", None]:
            alias = factoid.alias
            factoid = await self.get_factoid_entry(alias, ctx.guild.id)
            # Broken alias, shouldn't happen but is here just in case
            if not alias:
                raise FactoidNotFoundError(factoid=factoid.alias)

        embed = self.get_embed_from_factoid(factoid)
        # if the json doesn't include non embed argument, then don't send anything
        # otherwise send message text with embed
        plaintext_content = factoid.message if not embed else None
        mentions = auxiliary.construct_mention_string(ctx.message.mentions)

        content = " ".join(filter(None, [mentions, plaintext_content])) or None
        if content and len(content) > 2000:
            await auxiliary.send_deny_embed(
                message="I ran into an error sending that factoid: "
                + "The factoid message is longer than the discord size limit (2000)",
                channel=ctx.channel,
            )
            raise TooLongFactoidMessageError

        try:
            # define the message and send it
            message = await ctx.send(
                content=content,
                embed=embed,
            )
            # log it in the logging channel with type info and generic content
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "info",
                f"Sending factoid: {query} (triggered by {ctx.author} in #{ctx.channel.name})",
                send=True,
            )
            # If something breaks, also log it
        except discord.errors.HTTPException as e:
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not send factoid",
                exception=e,
            )
            # Sends the raw factoid instead of the embed as fallback
            message = await ctx.send(factoid.message)

        self.dispatch(ctx.author, message, factoid)

    def dispatch(self, author: discord.Member, message: discord.Message, factoid):
        """Sends factoid info into the irc relay

        Args:
            author (discord.Member): The invoker
            message (discord.Message): The message paired with the factoid
            factoid (Factoid): The factoid called
        """
        self.bot.dispatch(
            "factoid_event",
            munch.Munch(author=author, message=message, factoid=factoid),
        )

    # -- Factoid job related functions --
    async def kickoff_jobs(self):
        """Gets a list of cron jobs and starts them"""
        jobs = await self.models.FactoidJob.query.gino.all()
        for job in jobs:
            job_id = job.job_id
            self.cronjob_cache[job_id] = {}

            # This allows the task to be manually cancelled, preventing one more execution
            task = asyncio.create_task(self.cronjob(job))
            task = self.cronjob_cache[job_id]["task"] = task

    async def cronjob(self, job, ctx: commands.Context = None):
        """Run a cron job for a factoid

        Args:
            job (FactoidJob): The job to start
            ctx (commands.Context): The context, used for logging"""
        job_id = job.job_id
        self.cronjob_cache[job_id]["job"] = job

        while True:
            job = self.cronjob_cache.get(job_id)["job"]
            if not job:
                from_db = await self.models.FactoidJob.query.where(
                    self.models.FactoidJob.job_id == job_id
                ).gino.first()
                if not from_db:
                    # This factoid job has been deleted from the DB
                    await self.bot.logger.warning(
                        f"Cron job {job} has failed - factoid has been deleted from the DB"
                    )
                    if ctx:
                        await self.bot.guild_log(
                            ctx.guild,
                            "logging_channel",
                            "error",
                            f"Cron job {job} has failed - factoid has been deleted from the DB",
                        )
                    return
                job = from_db
                self.cronjob_cache[job_id]["job"] = job

            try:
                await aiocron.crontab(job.cron).next()
            except aiocron.CroniterBadCronError as e:
                await self.bot.logger.error(
                    "Could not await cron completion", exception=e
                )
                if ctx:
                    await self.bot.guild_log(
                        ctx.guild,
                        "logging_channel",
                        "error",
                        "Could not await cron job completion",
                        exception=e,
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

            # Get_embed accepts job as a factoid object
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
        aliases=["add"],
        description="Creates a factoid",
        usage="[factoid-name] [factoid-output] |optional-embed-json-upload|",
    )
    async def remember(self, ctx: commands.Context, factoid_name: str, *, message: str):
        """Command to add a factoid

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): Name of the factoid to add
            message (str): The message of the factoid
        """
        # Prevents factoids being created with html elements
        if re.match(r"<[^>/]+/?>", message) or re.match(r"<[^>/]+/?>", factoid_name):
            await auxiliary.send_deny_embed(
                "Cannot create factoids that contain HTML tags!", channel=ctx.channel
            )
            return

        embed_config = await util.get_json_from_attachments(ctx.message, as_string=True)
        await self.add_factoid(
            ctx,
            factoid_name=factoid_name.replace(" ", ""),
            guild=str(ctx.guild.id),
            message=message,
            embed_config=embed_config,
            alias=None,
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Deletes a factoid",
        aliases=["delete", "remove"],
        description="Deletes a factoid permanently, including its aliases",
        usage="[factoid-name]",
    )
    async def forget(self, ctx: commands.Context, factoid_name: str):
        """Command to remove a factoid

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): Name of the factoid to remove
        """

        factoid = await self.get_factoid_or_alias(factoid_name, str(ctx.guild.id))

        if not await self.delete_factoid(ctx, factoid.name):
            return

        # Removes associated aliases as well
        aliases = (
            await self.models.Factoid.query.where(
                self.models.Factoid.alias == factoid.name
            )
            .where(self.models.Factoid.guild == str(ctx.guild.id))
            .gino.all()
        )

        for alias in aliases:
            await self.delete_factoid(ctx, alias.name)

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Loops a factoid",
        description="Loops a pre-existing factoid",
        usage="[factoid-name] [channel] [cron-config]",
    )
    async def loop(
        self,
        ctx: commands.Context,
        factoid_name: str,
        channel: discord.TextChannel,
        *,
        cron_config: str,
    ):
        """Command to loop a factoid in a channel

        Args:
            ctx (commands.Context): Context of the invocation
            factoid_name (str): The name of the factoid to loop
            channel (discord.TextChannel): The channel to loop the factoid in
            cron_config (str): The cron config of the loop
        """

        factoid = await self.get_factoid_entry(factoid_name, str(ctx.guild.id))

        if not factoid:
            await auxiliary.send_deny_embed(
                message="That factoid does not exist", channel=ctx.channel
            )
            return

        if factoid.alias not in ["", None]:
            factoid = await self.get_factoid_entry(factoid.alias, str(ctx.guild.id))
            factoid_name = factoid.name

        # Check if loop already exists
        job = (
            await self.models.FactoidJob.join(self.models.Factoid)
            .select()
            .where(self.models.FactoidJob.channel == str(channel.id))
            .where(self.models.Factoid.name == factoid_name)
            .gino.first()
        )
        if job:
            await auxiliary.send_deny_embed(
                message="That factoid is already looping in this channel",
                channel=ctx.channel,
            )
            return

        cron_regex = (
            r"^((\*|([0-5]?\d|\*\/\d+)(-([0-5]?\d))?)(,\s*(\*|([0-5]?\d|\*\/\d+)(-([0-5]"
            + r"?\d))?)){0,59}\s+){4}(\*|([0-7]?\d|\*(\/[1-9]|[1-5]\d)|mon|tue|wed|thu|fri|sat|sun"
            + r")|\*\/[1-9])$"
        )

        # Only matches valid cron syntaxes (including some ugly ones,
        # except @ stuff since that isn't supported anyways)
        if not re.match(
            cron_regex,
            cron_config,
        ):
            await auxiliary.send_deny_embed(
                f"`{cron_config}` is not a valid cron configuration!",
                channel=ctx.channel,
            )
            return

        job = self.models.FactoidJob(
            factoid=factoid.factoid_id, channel=str(channel.id), cron=cron_config
        )
        await job.create()

        job_id = job.job_id
        self.cronjob_cache[job_id] = {}

        # This allows the task to be manually cancelled, preventing one more execution
        task = asyncio.create_task(self.cronjob(job, ctx))
        self.cronjob_cache[job_id]["task"] = task

        await auxiliary.send_confirm_embed(
            message="Factoid loop created", channel=ctx.channel
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Removes a factoid's loop config",
        description="De-loops a pre-existing factoid",
        usage="[factoid-name] [channel]",
    )
    async def deloop(
        self, ctx: commands.Context, factoid_name: str, channel: discord.TextChannel
    ):
        """Command to remove a factoid loop

        Args:
            ctx (commands.Context): Context of the invocation
            factoid_name (str): The name of the factoid to deloop
            channel (discord.TextChannel): The channel to deloop the factoid from
        """

        factoid = await self.get_factoid_or_alias(factoid_name, str(ctx.guild.id))

        job = (
            await self.models.FactoidJob.query.where(
                self.models.FactoidJob.channel == str(channel.id)
            )
            .where(self.models.Factoid.name == factoid.name)
            .gino.first()
        )
        if not job:
            await auxiliary.send_deny_embed(
                messge="That job does not exist", channel=ctx.channel
            )
            return

        job_id = job.job_id
        self.cronjob_cache[job_id]["task"].cancel()
        await job.delete()

        await auxiliary.send_confirm_embed(
            message="Loop job deleted",
            channel=ctx.channel,
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Displays loop config",
        description="Retrieves and displays the loop config for a specific factoid",
        usage="[factoid-name] [channel]",
    )
    async def job(
        self, ctx: commands.Context, factoid_name: str, channel: discord.TextChannel
    ):
        """Command to list info about a loop

        Args:
            ctx (commands.Context): Context of the invocation
            factoid_name (str): The name of the factoid
            channel (discord.TextChannel): The channel the factoid is looping in
        """
        # List jobs > Select jobs that have a matching text and channel
        job = (
            await self.models.FactoidJob.join(self.models.Factoid)
            .select()
            .where(self.models.FactoidJob.channel == str(channel.id))
            .where(self.models.Factoid.name == factoid_name)
            .gino.first()
        )
        if not job:
            await auxiliary.send_deny_embed(
                message="That job does not exist", channel=ctx.channel
            )
            return

        embed_label = ""
        if job.embed_config:
            embed_label = "(embed)"

        embed = discord.Embed(
            color=discord.Color.blurple(),
            title=f"Loop config for {factoid_name} {embed_label}",
            description=f'"{job.message}"',
        )

        embed.add_field(name="Channel", value=f"#{channel.name}")
        embed.add_field(name="Cron config", value=f"`{job.cron}`")

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        brief="Lists loop jobs",
        description="Lists all the currently registered loop jobs",
    )
    async def jobs(self, ctx: commands.Context):
        """Command ot list all factoid loop jobs

        Args:
            ctx (commands.Context): Context of the invocation
        """
        # Gets jobs for invokers guild
        jobs = (
            await self.models.FactoidJob.join(self.models.Factoid)
            .select()
            .where(self.models.Factoid.guild == str(ctx.guild.id))
            .gino.all()
        )
        if not jobs:
            await auxiliary.send_deny_embed(
                message="There are no registered factoid loop jobs for this guild",
                channel=ctx.channel,
            )
            return

        embed = discord.Embed(
            color=discord.Color.blurple(),
            title=f"Factoid loop jobs for {ctx.guild.name}",
        )
        for job in jobs[:10]:
            channel = self.bot.get_channel(int(job.channel))
            if not channel:
                continue
            embed.add_field(
                name=f"{job.name.lower()} - #{channel.name}",
                value=f"`{job.cron}`",
                inline=False,
            )

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        name="json",
        brief="Gets embed JSON",
        description="Gets embed JSON for a factoid",
        usage="[factoid-name]",
    )
    async def _json(self, ctx: commands.Context, factoid_name: str):
        """Gets the json of a factoid

        Args:
            ctx (commands.Context): Context of the invocation
            factoid_name (str): The name of the factoid
        """

        factoid = await self.get_factoid_or_alias(factoid_name, str(ctx.guild.id))

        if not factoid.embed_config:
            await auxiliary.send_deny_embed(
                message="There is no embed config for that factoid", channel=ctx.channel
            )
            return

        # Formats the json to have indents, then sends it to the channel it was called from
        formatted = json.dumps(json.loads(factoid.embed_config), indent=4)
        json_file = discord.File(
            io.StringIO(formatted),
            filename=f"{factoid.name}-factoid-embed-config-{datetime.datetime.utcnow()}.json",
        )

        await ctx.send(file=json_file)

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        brief="Gets information about a factoid",
        aliases=["aliases"],
        description="Returns information about a factoid (or the parent if it's an alias)",
        usage="[factoid-name]",
    )
    async def info(
        self,
        ctx: commands.Context,
        query: str,
    ):
        """Command to list info about a factoid

        Args:
            ctx (commands.Context): Context of the invocation
            query (str): The factoid name to query
        """

        # Gets the factoid if it exists
        factoid = await self.get_factoid_or_alias(query, str(ctx.guild.id))

        embed = discord.Embed(title=f"Info about `{factoid.name.lower()}`")

        # Parses list of aliases into a neat string
        aliases = (
            await self.models.Factoid.query.where(
                self.models.Factoid.alias == factoid.name
            )
            .where(self.models.Factoid.guild == str(ctx.guild.id))
            .gino.all()
        )
        # Awkward formatting of `, ` to save an if statement
        alias_list = "" if aliases else "None, "
        for alias in aliases:
            alias_list += f"`{alias.name.lower()}`, "

        # Adds all firleds to the embed
        embed.add_field(name="Aliases", value=alias_list[:-2])
        embed.add_field(name="Embed", value=bool(factoid.embed_config))
        embed.add_field(name="Contents", value=factoid.message)
        embed.add_field(name="Date of creation", value=factoid.time)

        # Finally, sends the factoid
        await ctx.send(embed=embed)

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        name="all",
        aliases=["lsf"],
        brief="List all factoids",
        description="Sends a list of all factoids, can take a file and hidden flag.",
        usage="[optional-flag]",
    )
    async def all_(self, ctx: commands.Context, *, flag: str = ""):
        """Command to list all factoids

        Args:
            ctx (commands.Context): Context of the invocation
            flag (str, optional): Can be "file", which will return a .yaml instead of a paste.
                                  Defaults to an empty string.
        """
        flag = flag.lower()
        # Makes sure no bad flag was passed
        if flag and not re.match(r"^(file hidden|hidden file|file|hidden)$", flag):
            await auxiliary.send_deny_embed(
                message=f"Uknown flag: `{flag.replace('hidden', '').replace('file', '')}`",
                channel=ctx.channel,
            )
            return

        # If cache exists
        cache = await self.check_lsf_cache(flag)
        if cache is not None and type(cache) == discord.File:
            # Returns cached .yaml file
            await ctx.send(file=cache)
            return

        # URL was passed
        if cache is not None:
            # Returns cached URL
            await auxiliary.send_confirm_embed(message=cache, channel=ctx.channel)
            return

        config = await self.bot.get_context_config(ctx)

        factoids = await self.get_all_factoids(str(ctx.guild.id), list_hidden=True)
        if not factoids:
            await auxiliary.send_deny_embed(
                message="No factoids found!", channel=ctx.channel
            )
            return

        # Gets a dict of aliases where
        # Aliased_factoid = ["list_of_aliases"]
        aliases = {}
        for factoid in factoids:
            if factoid.alias not in [None, ""]:
                # Append to aliases
                if factoid.alias in aliases:
                    aliases[factoid.alias].append(factoid.name)
                    continue

                aliases[factoid.alias] = [factoid.name]

        list_hidden = False
        if "hidden" in flag:
            if not ctx.author.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            list_hidden = True

        if "file" in flag or not config.extensions.factoids.linx_url.value:
            await self.send_factoids_as_file(ctx, factoids, aliases, list_hidden, flag)
            return

        html = await self.generate_html(ctx, factoids, aliases, list_hidden)
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

        try:
            url = await response.text()
            filename = url.split("/")[-1]
            url = url.replace(filename, f"selif/{filename}")

            # Creates cache
            self.factoid_all_cache[0] = {}
            self.factoid_all_cache[0]["url"] = url
            self.factoid_all_cache[0]["flags"] = flag

            # Returns the url
            await auxiliary.send_confirm_embed(message=url, channel=ctx.channel)

        except (gaierror, InvalidURL) as e:
            await self.send_factoids_as_file(ctx, factoids, aliases, list_hidden, flag)
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not render/send all-factoid HTML",
                exception=e,
            )

    async def generate_html(
        self, ctx: commands.Context, factoids: list, aliases: dict, list_hidden: bool
    ) -> str:
        """Method to generate the html file

        Args:
            ctx (commands.Context): The context, used for the guild name
            factoids (list): List of all factoids
            aliases (dict): A dictionary containing factoids and their aliases
            list_hidden (bool): Whether to list hidden factoids as well

        Returns:
            str - The result html file
        """

        list_items = ""
        for factoid in factoids:
            if not list_hidden and factoid.hidden:
                continue

            embed_text = " (embed)" if factoid.embed_config else ""

            # Skips aliases
            if factoid.alias not in [None, ""]:
                continue

            # If aliased
            if factoid.name in aliases:
                list_items += (
                    f"<li><code>{factoid.name} [{', '.join(aliases[factoid.name])}]{embed_text}"
                    + f" - {factoid.message}</code></li>"
                )

            # If not aliased
            else:
                list_items += (
                    f"<li><code>{factoid.name}{embed_text}"
                    + f" - {factoid.message}</code></li>"
                )

        body_contents = f"<ul>{list_items}</ul>"
        output = (
            f"""
        <!DOCTYPE html>
        <html>
        <body>
        <h3>Factoids for {ctx.guild.name}</h3>
        {body_contents}
        <style>"""
            + """
        ul {
            display: table; /* Make the entire list behave like a table */
            width: auto; /* Allow the list to adjust its width based on content */
        }

        ul li {
            display: table-row; /* Make each list item behave like a table row */
        }

        ul li:nth-child(even) {
            background-color: lightgray;
        }
        </style>
        </body>
        </html>
        """
        )
        return output

    async def send_factoids_as_file(
        self,
        ctx: commands.Context,
        factoids: list,
        aliases: dict,
        list_hidden: bool,
        flag: str,
    ):
        """Method to send the factoid list as a file instead of a paste

        Args:
            ctx (commands.Context): The context, used for the guild id
            factoids (list): List of all factoids
            aliases (dict): A dictionary containing factoids and their aliases
            list_hidden (bool): Whether to list hidden factoids as well
            flag (str): The flags passed to the command itself, passed for caching
        """

        output_data = []
        for factoid in factoids:
            if not list_hidden and factoid.hidden:
                continue
            # Skips aliases
            if factoid.alias not in [None, ""]:
                continue

            # If not aliased
            if factoid.name in aliases:
                data = {
                    "message": factoid.message,
                    "embed": bool(factoid.embed_config),
                    "aliases": ", ".join(aliases[factoid.name]),
                }

            # If aliased
            else:
                data = {"message": factoid.message, "embed": bool(factoid.embed_config)}

            output_data.append({factoid.name: data})

        if output_data == "[]":
            await auxiliary.send(message="No factoids found!", channel=ctx.channel)
        yaml_file = discord.File(
            io.StringIO(yaml.dump(output_data)),
            filename=f"factoids-for-server-{ctx.guild.id}-{datetime.datetime.utcnow()}.yaml",
        )

        # Creates cache
        self.factoid_all_cache[0] = {}
        self.factoid_all_cache[0]["file"] = [
            yaml.dump(output_data),
            f"factoids-for-server-{ctx.guild.id}-{datetime.datetime.utcnow()}.yaml",
        ]
        self.factoid_all_cache[0]["flags"] = flag

        # Sends the file
        await ctx.send(file=yaml_file)

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        aliases=["find"],
        brief="Searches a factoid",
        description="Searches a factoid by name and contents",
        usage="[optional-flag]",
    )
    async def search(self, ctx: commands.Context, *, query: str):
        """Commands to search a factoid

        Args:
            ctx (commands.Context): Context of the invokation
            query (str): The querry to look for
        """
        factoids = await self.get_all_factoids(str(ctx.guild.id), list_hidden=True)
        embed = discord.Embed(color=discord.Color.green())

        name_matches = "`"
        for factoid in factoids:
            if factoid.name and query in factoid.name:
                name_matches += f"{factoid.name}`, `"

        if name_matches == "`":
            name_matches = "No matches found!, `"

        embed.add_field(name="Name matches", value=name_matches[:-3], inline=False)

        content_matches = "`"
        for factoid in factoids:
            if (
                factoid.embed_config is not None
                and query in factoid.embed_config
                or query in factoid.message
            ):
                content_matches += f"{factoid.name}`, `"

            elif query in factoid.message:
                content_matches += f"{factoid.name}`, `"

        if content_matches == "`":
            content_matches = "No matches found!, `"

        embed.add_field(
            name="Content matches", value=content_matches[:-3], inline=False
        )

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Hides a factoid",
        description="Hides a factoid from showing in the all response",
        usage="[factoid-name]",
    )
    async def hide(
        self,
        ctx: commands.Context,
        factoid_name: str,
    ):
        """Command to hide a factoid from the .factoid all command

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): Name of the factoid to hide
        """

        factoid = await self.get_factoid_or_alias(factoid_name, str(ctx.guild.id))

        if factoid.hidden:
            await auxiliary.send_deny_embed(
                message="That factoid is already hidden", channel=ctx.channel
            )
            return

        await self.modify_factoid_call(factoid=factoid, hidden=True)

        await auxiliary.send_confirm_embed(
            message="That factoid is now hidden", channel=ctx.channel
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Unhides a factoid",
        description="Unhides a factoid from showing in the all response",
        usage="[factoid-name]",
    )
    async def unhide(
        self,
        ctx: commands.Context,
        factoid_name: str,
    ):
        """Command to unhide a factoid from the .factoid all list

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): The name of the factoid to unhide
        """
        factoid = await self.get_factoid_or_alias(factoid_name, str(ctx.guild.id))

        if not factoid.hidden:
            await auxiliary.send_deny_embed(
                message="That factoid is already unhidden", channel=ctx.channel
            )
            return

        await self.modify_factoid_call(factoid=factoid, hidden=False)

        await auxiliary.send_confirm_embed(
            message="That factoid is now unhidden", channel=ctx.channel
        )

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Adds a factoid alias",
        description="Adds an alternate way to call a factoid",
        usage="[factoid-name] [alias-name]",
    )
    async def alias(
        self,
        ctx: commands.Context,
        factoid_name: str,
        alias_name: str,
    ):
        """Command to add an alternate way of calling a factoid

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): The parent factoid name
            alias_name (str): The alias name
        """
        # Makes factoids caps insensitive

        # Gets the parent factoid
        factoid = await self.get_factoid_or_alias(factoid_name, str(ctx.guild.id))

        # Stops execution if the target is in the alias list already
        if await self.check_alias_recursion(
            ctx.channel, str(ctx.guild.id), factoid_name, alias_name
        ):
            return

        # Prevents recursing aliases because fuck that!
        if factoid.alias not in ["", None]:
            await auxiliary.send_deny_embed(
                "Can't set an alias for an alias!", channel=ctx.channel
            )
            return

        # Firstly check if the new entry already exists
        target_entry = await self.get_factoid_entry(alias_name, str(ctx.guild.id))

        # Handling if it exists already
        if target_entry:
            # Alias already present and points to the correct factoid
            if target_entry.alias == factoid.name:
                await auxiliary.send_deny_embed(
                    f"`{factoid.name.lower()}` already has `{target_entry.name.lower()}` set "
                    + "as an alias!",
                    channel=ctx.channel,
                )
                return

            # Confirms deletion of old entry
            if not await self.confirm_factoid_deletion(alias_name, ctx):
                return

            # If the target entry is the parent
            if target_entry.alias in ["", None]:
                # The first alias becomes the new parent
                # A more destructive way to do this would be to have the new parent have
                # the old aliases, but that would delete the previous parent and therefore
                # be more dangerous.

                # Gets list of all aliases
                aliases = (
                    await self.models.Factoid.query.where(
                        self.models.Factoid.alias == target_entry.name
                    )
                    .where(self.models.Factoid.guild == str(ctx.guild.id))
                    .gino.all()
                )

                # Don't make new parent if there isn't an alias for it
                if len(aliases) != 0:
                    # Modifies previous instance of alias to be the parent
                    alias_entry = await self.get_factoid_entry(
                        aliases[0].name, str(ctx.guild.id)
                    )

                    await self.modify_factoid_call(
                        factoid=alias_entry,
                        factoid_name=aliases[0].name,
                        message=target_entry.message,
                        embed_config=target_entry.embed_config,
                        alias="",
                    )

                    await self.handle_parent_change(ctx, aliases, aliases[0].name)

            # Removes the old alias entry
            await self.delete_factoid_call(target_entry)
            await self.handle_cache(str(ctx.guild.id), alias_name)

        # Finally, add the new alias
        await self.create_factoid_call(
            factoid_name=alias_name,
            guild=str(ctx.guild.id),
            message="",
            embed_config="",
            alias=factoid.name,
        )
        await auxiliary.send_confirm_embed(
            f"Successfully added the alias `{alias_name.lower()}` for `{factoid.name.lower()}`",
            channel=ctx.channel,
        )

    @util.with_typing
    @commands.guild_only()
    @factoid.command(
        brief="Deletes only an alias",
        description="Removes an alias from the group. Will never delete the actual factoid",
        usage="[factoid-name] [optional-new-parent]",
    )
    async def dealias(
        self, ctx: commands.Context, factoid_name: str, replacement_name: str = None
    ):
        """Command to remove an alias from the group, but never delete the parent

        Args:
            ctx (commands.Context): Context of the invocation
            factoid_name (str): The name of the factoid to remove
            replacement_name (str, optional): Name of new parent. Defaults to None.
        """

        factoid = await self.get_factoid_or_alias(factoid_name, str(ctx.guild.id))

        # -- Handling for aliases  --
        # (They just get deleted, no parent handling needs to be done)

        if factoid.name != factoid_name:
            await self.delete_factoid_call(
                await self.get_factoid_entry(factoid_name, str(ctx.guild.id))
            )
            await auxiliary.send_confirm_embed(
                f"Deleted the alias `{factoid_name.lower()}`", channel=ctx.channel
            )
            return

        # -- Handling for parents --

        # Gets list of aliases
        aliases = (
            await self.models.Factoid.query.where(
                self.models.Factoid.alias == factoid.name
            )
            .where(self.models.Factoid.guild == str(ctx.guild.id))
            .gino.all()
        )
        # Stop execution if there is no other parent to be assigned
        if len(aliases) == 0:
            await ctx.channel.send_deny_embed(
                f"`{factoid_name.lower()}` has no aliases", channel=ctx.channel
            )
            return

        # Converts the raw alias list to a list of alias names
        alias_list = []
        for alias in aliases:
            alias_list.append(alias.name)

        # Firstly checks if the replacement name is in the aliast list, if it wasn't specified
        # it defaults to None, both of which would assign a random value
        new_name = replacement_name if replacement_name in alias_list else alias_list[0]
        # If the value is specified (not None) and doesn't match the name, we know
        # the new entry is randomized
        if replacement_name and replacement_name != new_name:
            await auxiliary.send_deny_embed(
                message=f"I couldn't find the new parent `{replacement_name.lower()}`"
                + ", picking new parent at random",
                channel=ctx.channel,
            )

        await self.modify_factoid_call(
            factoid=await self.get_factoid_entry(new_name, str(ctx.guild.id)),
            factoid_name=new_name,
            message=factoid.message,
            embed_config=factoid.embed_config,
            alias="",
        )

        # Updates old aliases
        await self.handle_parent_change(ctx, aliases, new_name)
        await auxiliary.send_confirm_embed(
            f"Removed old instance, new parent: `{new_name.lower()}`",
            channel=ctx.channel,
        )

        # Finally deletes the parent
        await factoid.delete()
        await self.handle_cache(str(ctx.guild.id), factoid_name)

    @util.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Flushes the factoid cache",
        description="Flushes the factoid cache",
    )
    async def flush(self, ctx: commands.Context):
        """Command to flush the factoid cache

        Args:
            ctx (commands.Context): Context of the invokation
        """
        for item in self.factoid_cache:
            if item.startswith(str(ctx.guild.id)):
                del self.factoid_cache[item]

        await auxiliary.send_confirm_embed(
            message=f"Factoid cache for `{str(ctx.guild.id)}` succesfully flushed!",
            channel=ctx.channel,
        )
