"""
Name: Factoids
Info: Makes callable slices of text
Unit tests: No
Config: manage_roles, prefix
API: Linx
Databases: Postgres
Models: Factoid, FactoidJob
Subcommands: remember, forget, info, json, all, search, loop, deloop, job, jobs, hide, unhide,
             alias, dealias
Defines: has_manage_factoids_role
"""

from __future__ import annotations

import asyncio
import datetime
import io
import json
import re
from dataclasses import dataclass
from socket import gaierror
from typing import TYPE_CHECKING

import aiocron
import discord
import expiringdict
import ui
import yaml
from aiohttp.client_exceptions import InvalidURL
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, custom_errors, extensionconfig
from croniter import CroniterBadCronError
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot):
    """
    Define database tables, registers configs, registers extension
    """

    # Sets up the config
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="manage_roles",
        datatype="list",
        title="Manage factoids roles",
        description="The roles required to manage factoids",
        default=["Factoids"],
    )
    config.add(
        key="admin_roles",
        datatype="list",
        title="Admin factoids roles",
        description="The roles required to administrate factoids",
        default=["Admin"],
    )
    config.add(
        key="prefix",
        datatype="str",
        title="Factoid prefix",
        description="Prefix for calling factoids",
        default="?",
    )
    config.add(
        key="restricted_list",
        datatype="list",
        title="Restricted channels list",
        description="List of channel IDs that restricted factoids are allowed to be used in",
        default=[],
    )

    await bot.add_cog(
        FactoidManager(
            bot=bot,
            extension_name="factoids",
        )
    )
    bot.add_extension_config("factoids", config)


async def has_manage_factoids_role(ctx: commands.Context) -> bool:
    """A command check to determine if the invoker is allowed to modify basic factoids

    Args:
        ctx (commands.Context): The context the command was run

    Returns:
        bool: True if the command can be run, False if it can't
    """
    config = ctx.bot.guild_configs[str(ctx.guild.id)]
    return await has_given_factoids_role(
        ctx, config.extensions.factoids.manage_roles.value
    )


async def has_admin_factoids_role(ctx: commands.Context) -> bool:
    """A command check to determine if the invoker is allowed to modify factoid properties

    Args:
        ctx (commands.Context): The context the command was run

    Returns:
        bool: True if the command can be run, False if it can't
    """
    config = ctx.bot.guild_configs[str(ctx.guild.id)]
    return await has_given_factoids_role(
        ctx, config.extensions.factoids.admin_roles.value
    )


async def has_given_factoids_role(
    ctx: commands.Context, check_roles: list[str]
) -> bool:
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
    factoid_roles = []
    # Gets permitted roles
    for name in check_roles:
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


@dataclass
class CalledFactoid:
    """A class to allow keeping the original factoid name in tact
    Without having to call the database lookup function every time
    """

    original_call_str: str
    factoid_db_entry: bot.models.Factoid


class FactoidManager(cogs.MatchCog):
    """
    Manages all factoid features
    """

    CRON_REGEX = (
        r"^((\*|([0-5]?\d|\*\/\d+)(-([0-5]?\d))?)(,\s*(\*|([0-5]?\d|\*\/\d+)(-([0-5]"
        + r"?\d))?)){0,59}\s+){4}(\*|([0-7]?\d|\*(\/[1-9]|[1-5]\d)|mon|tue|wed|thu|fri|sat|sun"
        + r")|\*\/[1-9])$"
    )

    async def preconfig(self):
        """Preconfig for factoid jobs"""
        self.factoid_cache = expiringdict.ExpiringDict(
            max_len=100, max_age_seconds=1200
        )
        # set a hard time limit on repeated cronjob DB calls
        self.running_jobs = {}
        self.factoid_all_cache = expiringdict.ExpiringDict(
            max_len=1,
            max_age_seconds=86400,  # 24 hours, matches deletion on linx server
        )
        await self.bot.logger.send_log(
            message="Loading factoid jobs",
            level=LogLevel.DEBUG,
        )
        await self.kickoff_jobs()

    # -- DB calls --
    async def delete_factoid_call(self, factoid, guild: str):
        """Calls the db to delete a factoid

        Args:
            factoid (Factoid): The factoid to delete
            guild (str): The guild ID for cache handling
        """
        # Removes the `factoid all` cache since it has become outdated
        if guild in self.factoid_all_cache:
            del self.factoid_all_cache[guild]

        # Deloops the factoid first (if it's looped)
        jobs = await self.bot.models.FactoidJob.query.where(
            self.bot.models.FactoidJob.factoid == factoid.factoid_id
        ).gino.all()
        if jobs:
            for job in jobs:
                job_id = job.job_id
                # Cancels the job
                self.running_jobs[job_id]["task"].cancel()

                # Removes it from the cache
                del self.running_jobs[job_id]

                # Removes the DB entry
                await job.delete()

        await self.handle_cache(guild, factoid.name)
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

            Raises:
            custom_errors.TooLongFactoidMessageError:
                When the message argument is over 2k chars, discords limit
        """
        if len(message) > 2000:
            raise custom_errors.TooLongFactoidMessageError

        # Removes the `factoid all` cache since it has become outdated
        if guild in self.factoid_all_cache:
            del self.factoid_all_cache[guild]

        factoid = self.bot.models.Factoid(
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
    ):
        """Makes a DB call to modify a factoid

        Args:
            factoid (Factoid): Factoid to modify.
            factoid_name (str, optional): New factoid name. Defaults to None.
            message (str, optional): New factoid message. Defaults to None.
            embed_config (str, optional): Whether the factoid has an embed set up. Defaults to None.
            hidden (bool, optional): Whether the factoid is hidden. Defaults to None.
            alias (str, optional): New parent factoid. Defaults to None.

        Raises:
            custom_errors.TooLongFactoidMessageError:
                When the message argument is over 2k chars, discords limit
        """
        if len(factoid.message) > 2000:
            raise custom_errors.TooLongFactoidMessageError

        # Removes the `factoid all` cache since it has become outdated
        if factoid.guild in self.factoid_all_cache:
            del self.factoid_all_cache[factoid.guild]

        await factoid.update(
            name=factoid.name,
            message=factoid.message,
            embed_config=factoid.embed_config,
            hidden=factoid.hidden,
            protected=factoid.protected,
            disabled=factoid.disabled,
            restricted=factoid.restricted,
            alias=factoid.alias,
        ).apply()

        await self.handle_cache(factoid.guild, factoid.name)

    # -- Utility --
    async def confirm_factoid_deletion(
        self, factoid_name: str, ctx: commands.Context, fmt: str
    ) -> bool:
        """Confirms if a factoid should be deleted/modified

        Args:
            factoid_name (str): The factoid that is being prompted for deletion
            ctx (commands.Context): Used to return the message
            fmt (str): Formatting for the returned message

        Returns:
            (bool): Whether the factoid was deleted/modified
        """

        view = ui.Confirm()
        await view.send(
            message=(
                f"The factoid `{factoid_name}` already exists. Should I overwrite it?"
            ),
            channel=ctx.channel,
            author=ctx.author,
        )

        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return False

        if view.value is ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                message=f"The factoid `{factoid_name}` was not {fmt}.",
                channel=ctx.channel,
            )
            return False

        return True

    async def check_valid_factoid_contents(
        self, ctx: commands.Context, factoid_name: str, message: str
    ) -> str:
        """Makes sure the factoid contents are valid

        Args:
            ctx (commands.Context): Used to make sure that the .factoid remember invokation message
                                    didn't include any mentions
            factoid_name (str): The name to check
            message (str): The message to check

        Returns:
            str: The error message
        """

        # Prevents factoids from being created with any mentions
        if (
            ctx.message.mention_everyone  # @everyone
            or ctx.message.role_mentions  # @role
            or ctx.message.mentions  # @person
            or ctx.message.channel_mentions  # #Channel
        ):
            return "I cannot remember factoids with user/role/channel mentions"

        # Prevents factoids being created with html elements
        if re.search(r"<[^>]+>", message) or re.search(r"<[^>]+>", factoid_name):
            return "Cannot create factoids that contain HTML tags!"

        # Prevents factoids being created with spaces
        if " " in factoid_name:
            return "Cannot create factoids with names that contain spaces!"

        return None

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
            alias.alias = new_name
            await self.modify_factoid_call(factoid=alias)
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
            await self.bot.models.Factoid.query.where(
                self.bot.models.Factoid.alias == alias_name
            )
            .where(self.bot.models.Factoid.guild == guild)
            .gino.all()
        )

        # Returns arue if the factoid and alias name is the same (.factoid alias a a)
        if factoid_name == alias_name:
            await auxiliary.send_deny_embed(
                message="Can't set an alias for itself!", channel=channel
            )
            return True

        # Returns True if the target has the alias already
        # (.factoid alias b a, where b has a set already)
        if factoid_name in [alias.name for alias in factoid_aliases]:
            await auxiliary.send_deny_embed(
                message=f"`{alias_name}` already has `{factoid_name}`"
                + "set as an alias!",
                channel=channel,
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

    # -- Cache functions --
    async def handle_cache(self, guild: str, factoid_name: str):
        """Deletes factoid from the factoid cache

        Args:
            guild (str): The guild to get the cache key
            factoid_name (str): The name of the factoid to remove from the cache
        """
        key = self.get_cache_key(guild, factoid_name)

        if key in self.factoid_cache:
            del self.factoid_cache[key]

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
            guild (str, optional): The guild to get the factoids from.
                                   Defaults to None, where all guilds are returned instead.
            list_hidden (bool, optional): Whether to list hidden factoids as well.
                                          Defaults to False.

        Returns:
            list: List of factoids
        """
        # Gets factoids for a guild, including those that are hidden
        if guild and list_hidden:
            factoids = await self.bot.models.Factoid.query.where(
                self.bot.models.Factoid.guild == guild
            ).gino.all()

        # Gets factoids for a guild excluding the hidden ones
        elif guild and not list_hidden:
            factoids = (
                await self.bot.models.Factoid.query.where(
                    self.bot.models.Factoid.guild == guild
                )
                # hiding hidden factoids
                # pylint: disable=C0121
                .where(self.bot.models.Factoid.hidden == False).gino.all()
            )

        # Gets ALL factoids for ALL guilds
        else:
            factoids = await self.bot.db.all(self.bot.models.Factoid.query)

        # Sorts them alphabetically
        if factoids:
            factoids.sort(key=lambda factoid: factoid.name)

        return factoids

    async def get_raw_factoid_entry(self, factoid_name: str, guild: str):
        """Searches the db for a factoid by its name, does NOT follow aliases

        Args:
            factoid_name (str): The name of the factoid to get
            guild (str): The id of the guild for the factoid

        Returns:
            Factoid: The factoid
        """
        cache_key = self.get_cache_key(guild, factoid_name.lower())
        factoid = self.factoid_cache.get(cache_key)
        # If the factoid isn't cached
        if not factoid:
            factoid = (
                await self.bot.models.Factoid.query.where(
                    self.bot.models.Factoid.name == factoid_name.lower()
                )
                .where(self.bot.models.Factoid.guild == guild)
                .gino.first()
            )

            # If the factoid doesn't exist
            if not factoid:
                raise custom_errors.FactoidNotFoundError(factoid=factoid_name)

            # Caches it
            self.factoid_cache[cache_key] = factoid

        return factoid

    async def get_factoid(self, factoid_name: str, guild: str):
        """Gets the factoid from the DB, follows aliases

        Args:
            factoid_name (str): The name of the factoid to get
            guild (str): The id of the guild for the factoid

        Raises:
            custom_errors.FactoidNotFoundError: If the factoid wasn't found

        Returns:
            Factoid: The factoid
        """
        factoid = await self.get_raw_factoid_entry(factoid_name, guild)

        # Handling if the call is an alias
        if factoid and factoid.alias not in ["", None]:
            factoid = await self.get_raw_factoid_entry(factoid.alias, guild)
            factoid_name = factoid.name

        if not factoid:
            raise custom_errors.FactoidNotFoundError(factoid=factoid_name)

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
            factoid = await self.get_factoid(factoid_name, guild)
            if factoid.protected:
                await auxiliary.send_deny_embed(
                    message=f"`{factoid.name}` is protected and cannot be modified",
                    channel=ctx.channel,
                )
                return
            name = factoid.name.lower()  # Name of the parent

        # Adds the factoid if it doesn't exist already
        except custom_errors.FactoidNotFoundError:
            # If remember was called with an embed but not a message and the factoid does not exist
            if not message:
                await auxiliary.send_deny_embed(
                    message="You did not provide the factoid message!",
                    channel=ctx.channel,
                )
                return

            await self.create_factoid_call(
                factoid_name=name,
                guild=guild,
                message=message,
                embed_config=embed_config,
                alias=alias,
            )

        # Modifies the factoid if it already exists
        else:
            fmt = "modified"
            # Confirms modification
            if await self.confirm_factoid_deletion(factoid_name, ctx, fmt) is False:
                return

            # Modifies the old entry
            factoid = await self.get_raw_factoid_entry(name, str(ctx.guild.id))
            factoid.name = name
            # if no message was supplied, keep the original factoid's message.
            if message:
                factoid.message = message
            factoid.embed_config = embed_config
            factoid.alias = alias
            await self.modify_factoid_call(factoid=factoid)

        # Removes the factoid from the cache
        await self.handle_cache(guild, name)

        await auxiliary.send_confirm_embed(
            message=f"Successfully {fmt} the factoid `{factoid_name}`",
            channel=ctx.channel,
        )

    async def delete_factoid(
        self, ctx: commands.Context, called_factoid: CalledFactoid
    ) -> bool:
        """Deletes a factoid with confirmation

        Args:
            ctx (commands.Context): Context to send the confirmation message to
            factoid_name (CalledFactoid): The factoid to remove

        Returns:
            (bool): Whether the factoid was deleted
        """
        factoid = await self.get_raw_factoid_entry(
            called_factoid.factoid_db_entry.name, str(ctx.guild.id)
        )

        view = ui.Confirm()
        await view.send(
            message=(
                f"This will remove the factoid `{called_factoid.original_call_str}` "
                "and all of it's aliases forever. Are you sure?"
            ),
            channel=ctx.channel,
            author=ctx.author,
        )

        await view.wait()
        if view.value is ui.ConfirmResponse.TIMEOUT:
            return False

        if view.value is ui.ConfirmResponse.DENIED:
            await auxiliary.send_deny_embed(
                message=f"Factoid `{called_factoid.original_call_str}` was not deleted",
                channel=ctx.channel,
            )
            return False

        await self.delete_factoid_call(factoid, str(ctx.guild.id))

        # Don't send the confirmation message if this is an alias either
        await auxiliary.send_confirm_embed(
            (
                f"Successfully deleted the factoid `{called_factoid.original_call_str}`"
                "and all of it's aliases"
            ),
            channel=ctx.channel,
        )
        return True

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
            custom_errors.FactoidNotFoundError: Raised if a broken alias is present in the DB
            custom_errors.TooLongFactoidMessageError:
                Raised when the raw message content is over discords 2000 char limit
        """
        if not ctx.guild:
            return
        # Checks if the first word of the content after the prefix is a valid factoid
        # Replaces \n with spaces so factoid can be called even with newlines
        query = message_content[1:].replace("\n", " ").split(" ")[0].lower()
        try:
            factoid = await self.get_factoid(query, str(ctx.guild.id))

        except custom_errors.FactoidNotFoundError:
            await self.bot.logger.send_log(
                message=f"Invalid factoid call {query} from {ctx.guild.id}",
                level=LogLevel.DEBUG,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
            )
            return

        # Checking for disabled or restricted
        if factoid.disabled:
            return

        if (
            factoid.restricted
            and str(ctx.channel.id)
            not in config.extensions.factoids.restricted_list.value
        ):
            return

        embed = self.get_embed_from_factoid(factoid)
        # if the json doesn't include non embed argument, then don't send anything
        # otherwise send message text with embed
        try:
            plaintext_content = factoid.message if not embed else None
        except ValueError:
            # The not embed causes a ValueError in certain cases. This ensures fallback works
            plaintext_content = factoid.message
        mentions = auxiliary.construct_mention_string(ctx.message.mentions)

        content = " ".join(filter(None, [mentions, plaintext_content])) or None
        if content and len(content) > 2000:
            await auxiliary.send_deny_embed(
                message="I ran into an error sending that factoid: "
                + "The factoid message is longer than the discord size limit (2000)",
                channel=ctx.channel,
            )
            raise custom_errors.TooLongFactoidMessageError

        try:
            # define the message and send it
            await ctx.reply(content=content, embed=embed, mention_author=not mentions)
            # log it in the logging channel with type info and generic content
            config = self.bot.guild_configs[str(ctx.guild.id)]
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message=(
                    f"Sending factoid: {query} (triggered by {ctx.author} in"
                    f" #{ctx.channel.name})"
                ),
                level=LogLevel.INFO,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
                channel=log_channel,
            )
        # If something breaks, also log it
        except discord.errors.HTTPException as exception:
            config = self.bot.guild_configs[str(ctx.guild.id)]
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message="Could not send factoid",
                level=LogLevel.ERROR,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
                channel=log_channel,
                exception=exception,
            )
            # Sends the raw factoid instead of the embed as fallback
            await ctx.reply(
                f"{mentions+' ' if mentions else ''}{factoid.message}",
                mention_author=not mentions,
            )

        await self.send_to_irc(ctx.channel, ctx.message, factoid.message)

    async def send_to_irc(
        self,
        channel: discord.abc.Messageable,
        message: discord.Message,
        factoid_message: str,
    ) -> None:
        """Send a factoid to IRC channel, if it was called in a linked channel

        Args:
            ctx (discord.abc.Messageable): The channel the factoid was sent in
            message (discord.Message): The message object of the invocation
            factoid_message (str): The text of the factoid to send
        """
        # Don't attempt to send a message if irc if irc is disabled
        irc_config = getattr(self.bot.file_config.api, "irc")
        if not irc_config.enable_irc:
            return None

        await self.bot.irc.irc_cog.handle_factoid(
            channel=channel,
            discord_message=message,
            factoid_message=factoid_message,
        )

    # -- Factoid job related functions --
    async def kickoff_jobs(self):
        """Gets a list of cron jobs and starts them"""
        jobs = await self.bot.models.FactoidJob.query.gino.all()
        for job in jobs:
            job_id = job.job_id
            self.running_jobs[job_id] = {}

            # This allows the task to be manually cancelled, preventing one more execution
            task = asyncio.create_task(self.cronjob(job))
            task = self.running_jobs[job_id]["task"] = task

    async def cronjob(self, job, ctx: commands.Context = None):
        """Run a cron job for a factoid

        Args:
            job (FactoidJob): The job to start
            ctx (commands.Context): The context, used for logging
        """
        job_id = job.job_id
        self.running_jobs[job_id]["job"] = job

        while True:
            job = self.running_jobs.get(job_id)["job"]
            if not job:
                from_db = await self.bot.models.FactoidJob.query.where(
                    self.bot.models.FactoidJob.job_id == job_id
                ).gino.first()
                if not from_db:
                    # This factoid job has been deleted from the DB
                    log_channel = None
                    log_context = None

                    if ctx:
                        config = self.bot.guild_configs[str(ctx.guild.id)]
                        channel = config.get("logging_channel")
                        log_context = LogContext(guild=ctx.guild, channel=ctx.channel)

                    await self.bot.logger.send_log(
                        message=(
                            f"Cron job {job} has failed - factoid has been deleted from"
                            " the DB"
                        ),
                        level=LogLevel.WARNING,
                        channel=channel,
                        context=log_context,
                    )

                    return
                job = from_db
                self.running_jobs[job_id]["job"] = job

            try:
                await aiocron.crontab(job.cron).next()

            except CroniterBadCronError as exception:
                log_channel = None
                log_context = None

                if ctx:
                    config = self.bot.guild_configs[str(ctx.guild.id)]
                    channel = config.get("logging_channel")
                    log_context = LogContext(guild=ctx.guild, channel=ctx.channel)

                await self.bot.logger.send_log(
                    message="Could not await cron completion",
                    level=LogLevel.ERROR,
                    channel=log_channel,
                    context=log_context,
                    exception=exception,
                )

                await asyncio.sleep(300)

            factoid = await self.bot.models.Factoid.query.where(
                self.bot.models.Factoid.factoid_id == job.factoid
            ).gino.first()
            if not factoid:
                log_channel = None
                log_context = None

                if ctx:
                    config = self.bot.guild_configs[str(ctx.guild.id)]
                    channel = config.get("logging_channel")
                    log_context = LogContext(guild=ctx.guild, channel=ctx.channel)

                await self.bot.logger.send_log(
                    message=(
                        "Could not find factoid referenced by job - will retry after"
                        " waiting"
                    ),
                    level=LogLevel.WARNING,
                    channel=log_channel,
                    context=log_context,
                )
                continue

            # Checking for disabled or restricted
            if factoid.disabled:
                return

            if (
                factoid.restricted
                and str(ctx.channel.id)
                not in config.extensions.factoids.restricted_list.value
            ):
                return

            # Get_embed accepts job as a factoid object
            embed = self.get_embed_from_factoid(factoid)
            try:
                content = factoid.message if not embed else None
            except ValueError:
                # The not embed causes a ValueError in certian places. This ensures fallback works
                content = factoid.message

            channel = self.bot.get_channel(int(job.channel))
            if not channel:
                log_channel = None
                log_context = None

                if ctx:
                    config = self.bot.guild_configs[str(ctx.guild.id)]
                    channel = config.get("logging_channel")
                    log_context = LogContext(guild=ctx.guild, channel=ctx.channel)

                await self.bot.logger.send_log(
                    message=(
                        "Could not find channel to send factoid cronjob - will retry"
                        " after waiting"
                    ),
                    level=LogLevel.WARNING,
                    channel=log_channel,
                    context=log_context,
                )
                continue

            try:
                message = await channel.send(content=content, embed=embed)

            except discord.errors.HTTPException as exception:
                config = self.bot.guild_configs[str(ctx.guild.id)]
                log_channel = config.get("logging_channel")
                await self.bot.logger.send_log(
                    message="Could not send looped factoid",
                    level=LogLevel.ERROR,
                    context=LogContext(guild=ctx.guild, channel=ctx.channel),
                    channel=log_channel,
                    exception=exception,
                )
                # Sends the raw factoid instead of the embed as fallback
                message = await channel.send(content=factoid.message)

            await self.send_to_irc(channel, message, factoid.message)

    @commands.group(
        brief="Executes a factoid command",
        description="Executes a factoid command",
    )
    async def factoid(self, ctx):
        """Method to create the factoid command group."""

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Creates a factoid",
        aliases=["add"],
        description="Creates a factoid",
        usage="[factoid-name] [factoid-output] |optional-embed-json-upload|",
    )
    async def remember(
        self, ctx: commands.Context, factoid_name: str, *, message: str = ""
    ):
        """Command to add a factoid

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): Name of the factoid to add
            message (str): The message of the factoid
        """
        # Checks if contents and name are valid
        error_message = await self.check_valid_factoid_contents(
            ctx, factoid_name, message
        )
        if error_message is not None:
            await auxiliary.send_deny_embed(message=error_message, channel=ctx.channel)
            return

        embed_config = await auxiliary.get_json_from_attachments(
            ctx.message, as_string=True
        )

        if not embed_config and not message:
            await auxiliary.send_deny_embed(
                message="You did not provide the factoid message!", channel=ctx.channel
            )
            return

        if embed_config and message == "":
            message = None

        await self.add_factoid(
            ctx,
            factoid_name=factoid_name,
            guild=str(ctx.guild.id),
            message=message,
            embed_config=embed_config if embed_config else "",
            alias=None,
        )

    @auxiliary.with_typing
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

        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid.name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        factoid_called = CalledFactoid(
            original_call_str=factoid_name, factoid_db_entry=factoid
        )

        if not await self.delete_factoid(ctx, factoid_called):
            return

        # Removes associated aliases as well
        aliases = (
            await self.bot.models.Factoid.query.where(
                self.bot.models.Factoid.alias == factoid.name
            )
            .where(self.bot.models.Factoid.guild == str(ctx.guild.id))
            .gino.all()
        )
        for alias in aliases:
            await self.delete_factoid_call(alias, str(ctx.guild.id))

    @auxiliary.with_typing
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
        config = self.bot.guild_configs[str(ctx.guild.id)]
        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        if factoid.disabled:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is disabled and new loops cannot be made",
                channel=ctx.channel,
            )
            return

        if (
            factoid.restricted
            and str(channel.id) not in config.extensions.factoids.restricted_list.value
        ):
            await auxiliary.send_deny_embed(
                message=(
                    f"`{factoid_name}` is restricted "
                    f"and cannot be used in {channel.mention}"
                ),
                channel=ctx.channel,
            )
            return

        # Check if loop already exists
        job = (
            await self.bot.models.FactoidJob.join(self.bot.models.Factoid)
            .select()
            .where(self.bot.models.FactoidJob.channel == str(channel.id))
            .where(self.bot.models.Factoid.name == factoid.name)
            .gino.first()
        )
        if job:
            await auxiliary.send_deny_embed(
                message="That factoid is already looping in this channel",
                channel=ctx.channel,
            )
            return

        # Only matches valid cron syntaxes (including some ugly ones,
        # except @ stuff since that isn't supported by cronitor anyways)
        if not re.match(
            self.CRON_REGEX,
            cron_config,
        ):
            await auxiliary.send_deny_embed(
                message=f"`{cron_config}` is not a valid cron configuration!",
                channel=ctx.channel,
            )
            return

        job = self.bot.models.FactoidJob(
            factoid=factoid.factoid_id, channel=str(channel.id), cron=cron_config
        )
        await job.create()

        job_id = job.job_id
        self.running_jobs[job_id] = {}

        # This allows the task to be manually cancelled, preventing one more execution
        task = asyncio.create_task(self.cronjob(job, ctx))
        self.running_jobs[job_id]["task"] = task

        await auxiliary.send_confirm_embed(
            message="Factoid loop created", channel=ctx.channel
        )

    @auxiliary.with_typing
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

        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is already protected",
                channel=ctx.channel,
            )
            return

        job = (
            await self.bot.models.FactoidJob.query.where(
                self.bot.models.FactoidJob.channel == str(channel.id)
            )
            .where(self.bot.models.Factoid.name == factoid.name)
            .gino.first()
        )
        if not job:
            await auxiliary.send_deny_embed(
                message="That job does not exist", channel=ctx.channel
            )
            return

        job_id = job.job_id
        # Stops the job
        self.running_jobs[job_id]["task"].cancel()
        # Deletes it
        await job.delete()

        await auxiliary.send_confirm_embed(
            message="Loop job deleted",
            channel=ctx.channel,
        )

    @auxiliary.with_typing
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
        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        # List jobs > Select jobs that have a matching text and channel
        job = (
            await self.bot.models.FactoidJob.join(self.bot.models.Factoid)
            .select()
            .where(self.bot.models.FactoidJob.channel == str(channel.id))
            .where(self.bot.models.Factoid.name == factoid.name)
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

        embed = auxiliary.generate_basic_embed(
            color=discord.Color.blurple(),
            title=f"Loop config for `{factoid_name}` {embed_label}",
            description=f'"{job.message}"',
        )

        embed.add_field(name="Channel", value=f"#{channel.name}")
        embed.add_field(name="Cron config", value=f"`{job.cron}`")

        await ctx.send(embed=embed)

    @auxiliary.with_typing
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
            await self.bot.models.FactoidJob.join(self.bot.models.Factoid)
            .select()
            .where(self.bot.models.Factoid.guild == str(ctx.guild.id))
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

    @auxiliary.with_typing
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

        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if not factoid.embed_config:
            await auxiliary.send_deny_embed(
                message=f"There is no embed config for `{factoid_name}`",
                channel=ctx.channel,
            )
            return

        # Formats the json to have indents, then sends it to the channel it was called from
        formatted = json.dumps(json.loads(factoid.embed_config), indent=4)
        json_file = discord.File(
            io.StringIO(formatted),
            filename=(
                f"{factoid.name}-factoid-embed-config-{datetime.datetime.utcnow()}.json"
            ),
        )

        await ctx.send(file=json_file)

    @auxiliary.with_typing
    @commands.guild_only()
    @factoid.command(
        brief="Gets information about a factoid",
        aliases=["aliases"],
        description=(
            "Returns information about a factoid (or the parent if it's an alias)"
        ),
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
        factoid = await self.get_factoid(query, str(ctx.guild.id))

        embed = discord.Embed(title=f"Info about `{query}`")

        # Parses list of aliases into a neat string
        aliases = (
            await self.bot.models.Factoid.query.where(
                self.bot.models.Factoid.alias == factoid.name
            )
            .where(self.bot.models.Factoid.guild == str(ctx.guild.id))
            .gino.all()
        )

        # Add and sort all aliases to a comma separated string
        aliases.append(factoid)
        alias_list = (
            "None"
            if not aliases
            else ", ".join(sorted([f"`{alias.name.lower()}`" for alias in aliases]))
        )

        # Gets the factoids loop jobs
        jobs = await self.bot.models.FactoidJob.query.where(
            self.bot.models.FactoidJob.factoid == factoid.factoid_id
        ).gino.all()

        # Adds all fields to the embed
        embed.add_field(name="Aliases", value=alias_list)
        embed.add_field(name="Embed", value=bool(factoid.embed_config))
        embed.add_field(name="Contents", value=factoid.message)
        embed.add_field(name="Date of creation", value=factoid.time)

        # Get all the special properties of a factoid, if any are set
        factoid_properties = ["hidden", "restricted", "disabled", "protected"]
        factoid_string = ", ".join(
            property
            for property in factoid_properties
            if getattr(factoid, property, False)
        )
        result = factoid_string if factoid_string else "None"
        embed.add_field(name="Properties", value=result)

        if jobs:
            for job in jobs[:10]:
                channel = self.bot.get_channel(int(job.channel))
                if not channel:
                    continue
                embed.add_field(
                    name=f"**Loop:** #{channel.name}",
                    value=f"`{job.cron}`\n",
                    inline=False,
                )

        # Finally, sends the factoid
        await ctx.send(embed=embed)

    @auxiliary.with_typing
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
                                  Can also be "hidden", which will return only hidden factoids.
                                  Defaults to an empty string.

        Raises:
            commands.MissingPermission: Raised when someone tries to call .factoid all with
                                        the hidden flag without administrator permissions
        """
        flags = flag.lower().split()
        guild = str(ctx.guild.id)

        # Gets the url from the cache if the invokation doesn't contain flags
        if (
            "file" not in flags
            and "hidden" not in flags
            and guild in self.factoid_all_cache
        ):
            url = self.factoid_all_cache[guild]["url"]
            await auxiliary.send_confirm_embed(message=url, channel=ctx.channel)
            return

        factoids = await self.get_all_factoids(guild, list_hidden=True)
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

        list_only_hidden = False
        if "hidden" in flags:
            if not ctx.author.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

            list_only_hidden = True

        if "file" in flags or not self.bot.file_config.api.api_url.linx:
            await self.send_factoids_as_file(
                ctx, factoids, aliases, list_only_hidden, flag
            )
            return

        try:
            # -Tries calling the api-
            html = await self.generate_html(ctx, factoids, aliases, list_only_hidden)
            # If there are no applicable factoids
            if html is None:
                await auxiliary.send_deny_embed(
                    message="No factoids found!", channel=ctx.channel
                )
                return

            headers = {
                "Content-Type": "text/plain",
            }
            response = await self.bot.http_functions.http_call(
                "put",
                self.bot.file_config.api.api_url.linx,
                headers=headers,
                data=io.StringIO(html),
                get_raw_response=True,
            )
            url = response["text"]
            filename = url.split("/")[-1]
            url = url.replace(filename, f"selif/{filename}")

            # Returns the url
            await auxiliary.send_confirm_embed(message=url, channel=ctx.channel)

            # Creates cache if hidden factoids weren't called
            if not list_only_hidden:
                self.factoid_all_cache[str(ctx.guild.id)] = {}
                self.factoid_all_cache[str(ctx.guild.id)]["url"] = url

        # If an error happened while calling the api
        except (gaierror, InvalidURL) as exception:
            config = self.bot.guild_configs[str(ctx.guild.id)]
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message="Could not render/send all-factoid HTML",
                level=LogLevel.ERROR,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
                channel=log_channel,
                exception=exception,
            )

            await self.send_factoids_as_file(
                ctx, factoids, aliases, list_only_hidden, flag
            )

    async def generate_html(
        self,
        ctx: commands.Context,
        factoids: list,
        aliases: dict,
        list_only_hidden: bool,
    ) -> str:
        """Method to generate the html file contents

        Args:
            ctx (commands.Context): The context, used for the guild name
            factoids (list): List of all factoids
            aliases (dict): A dictionary containing factoids and their aliases
            list_only_hidden (bool): Whether to list only hidden factoids

        Returns:
            str - The result html file
        """

        body_contents = ""
        for factoid in factoids:
            if (
                list_only_hidden
                and not factoid.hidden
                or not list_only_hidden
                and factoid.hidden
            ):
                continue

            # Formatting
            embed_text = " (embed)" if factoid.embed_config else ""

            # Skips aliases
            if factoid.alias not in [None, ""]:
                continue

            # If aliased
            if factoid.name in aliases:
                body_contents += (
                    f"<li><code>{factoid.name} [{', '.join(aliases[factoid.name])}]{embed_text}"
                    + f" - {factoid.message}</code></li>"
                )

            # If not aliased
            else:
                body_contents += (
                    f"<li><code>{factoid.name}{embed_text}"
                    + f" - {factoid.message}</code></li>"
                )
        if body_contents == "":
            return None

        body_contents = f"<ul>{body_contents}</ul>"
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
            display: table;
            width: auto;
        }

        ul li {
            display: table-row;
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
        list_only_hidden: bool,
        flag: str,
    ):
        """Method to send the factoid list as a file instead of a paste

        Args:
            ctx (commands.Context): The context, used for the guild id
            factoids (list): List of all factoids
            aliases (dict): A dictionary containing factoids and their aliases
            list_only_hidden (bool): Whether to list only hidden factoids
            flag (str): The flags passed to the command itself, passed for caching
        """

        output_data = []
        for factoid in factoids:
            # Handles hidden factoids
            if (
                list_only_hidden
                and not factoid.hidden
                or not list_only_hidden
                and factoid.hidden
            ):
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

        if not output_data:
            await auxiliary.send_deny_embed(
                message="No factoids found!", channel=ctx.channel
            )
            return

        yaml_file = discord.File(
            io.StringIO(yaml.dump(output_data)),
            filename=(
                f"factoids-for-server-{ctx.guild.id}-{datetime.datetime.utcnow()}.yaml"
            ),
        )

        # Sends the file
        await ctx.send(file=yaml_file)

    @auxiliary.with_typing
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
        query = query.lower()
        guild = str(ctx.guild.id)

        if len(query) < 3:
            await auxiliary.send_deny_embed(
                message="Please enter at least 3 characters for the search query!",
                channel=ctx.channel,
            )
            return

        factoids = await self.get_all_factoids(guild, list_hidden=False)
        # Makes query lowercase, makes sure you can't search for JSON elements
        embed = discord.Embed(color=discord.Color.green())
        num_of_matches = 0

        # - Name matches -
        name_matches = "`"
        for factoid in factoids:
            # Hard limit of 10
            if num_of_matches > 10:
                name_matches = name_matches[:-2] + " more...---"
                break

            if not factoid.alias and query in factoid.name.lower():
                name_matches += f"{factoid.name}`, `"
                num_of_matches += 1

        if name_matches == "`":
            name_matches = "No matches found!, `"

        # Adds name matches to the embed
        embed.add_field(name="Name matches", value=name_matches[:-3], inline=False)

        # - Content matches -
        num_of_matches = 0
        content_matches = "`"
        for factoid in factoids:
            # Hard limit of 10
            if num_of_matches > 10:
                content_matches = content_matches[:-2] + " more...---"
                break

            if factoid.embed_config is not None and (
                any(word in factoid.embed_config.lower() for word in query.split())
                or any(word in factoid.message.lower() for word in query.split())
            ):
                content_matches += f"{factoid.name}`, `"
                num_of_matches += 1

        if content_matches == "`":
            content_matches = "No matches found!   "

        # Adds content matches to the embed
        embed.add_field(
            name="Content matches", value=content_matches[:-3], inline=False
        )

        # Finally, send the embed
        await ctx.send(embed=embed)

    @auxiliary.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Adds a factoid alias",
        description="Adds an alternate way to call a factoid",
        usage="[new-alias-name] [original-factoid-name]",
    )
    async def alias(
        self,
        ctx: commands.Context,
        alias_name: str,
        factoid_name: str,
    ):
        """Command to add an alternate way of calling a factoid

        Args:
            ctx (commands.Context): Context of the invokation
            alias_name (str): The new alias name to create
            factoid_name (str): The original factoid name to add alias to

        """
        # Makes factoids caps insensitive

        # Gets the parent factoid
        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid.name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        # Stops execution if the target is in the alias list already
        if await self.check_alias_recursion(
            ctx.channel, str(ctx.guild.id), factoid_name, alias_name
        ):
            return

        # Prevents recursing aliases because fuck that!
        # This should never be run, a bug exists in get_factoid, or a database error exist
        # if this ever runs
        if factoid.alias not in ["", None]:
            await auxiliary.send_deny_embed(
                message="Can't set an alias for an alias!", channel=ctx.channel
            )
            return

        try:
            # Firstly check if the new entry already exists
            target_entry = await self.get_raw_factoid_entry(
                alias_name, str(ctx.guild.id)
            )

        # No handling needs to be done if it doesn't exist
        except custom_errors.FactoidNotFoundError:
            pass

        # Handling if it does already exist
        else:
            # Alias already present and points to the correct factoid
            if target_entry.alias == factoid.name:
                await auxiliary.send_deny_embed(
                    f"`{factoid_name}` already has `{alias_name}` set as an alias!",
                    channel=ctx.channel,
                )
                return

            # Confirms deletion of old entry
            if not await self.confirm_factoid_deletion(alias_name, ctx, "replaced"):
                return

            # If the target entry is the parent
            if target_entry.alias in ["", None]:
                # The first alias becomes the new parent
                # A more destructive way to do this would be to have the new parent have
                # the old aliases, but that would delete the previous parent and therefore
                # be more dangerous.

                # Gets list of all aliases
                aliases = (
                    await self.bot.models.Factoid.query.where(
                        self.bot.models.Factoid.alias == target_entry.name
                    )
                    .where(self.bot.models.Factoid.guild == str(ctx.guild.id))
                    .gino.all()
                )

                # Don't make new parent if there isn't an alias for it
                if len(aliases) != 0:
                    # Modifies previous instance of alias to be the parent
                    alias_entry = await self.get_raw_factoid_entry(
                        aliases[0].name, str(ctx.guild.id)
                    )

                    alias_entry.name = aliases[0].name
                    alias_entry.message = target_entry.message
                    alias_entry.embed_config = target_entry.embed_config
                    alias_entry.alias = None

                    await self.modify_factoid_call(factoid=alias_entry)

                    await self.handle_parent_change(ctx, aliases, aliases[0].name)

            # Removes the old alias entry
            await self.delete_factoid_call(target_entry, str(ctx.guild.id))

        # Finally, add the new alias
        await self.create_factoid_call(
            factoid_name=alias_name,
            guild=str(ctx.guild.id),
            message="",
            embed_config="",
            alias=factoid.name,
        )
        await auxiliary.send_confirm_embed(
            message=f"Successfully added the alias `{alias_name}` for"
            + f" `{factoid_name}`",
            channel=ctx.channel,
        )

    @auxiliary.with_typing
    @commands.guild_only()
    @factoid.command(
        brief="Deletes only an alias",
        description=(
            "Removes an alias from the group. Will never delete the actual factoid"
        ),
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

        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid.name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        # -- Handling for aliases  --
        # (They just get deleted, no parent handling needs to be done)

        if factoid.name.lower() != factoid_name.lower():
            await self.delete_factoid_call(
                await self.get_raw_factoid_entry(factoid_name, str(ctx.guild.id)),
                str(ctx.guild.id),
            )
            await auxiliary.send_confirm_embed(
                message=f"Deleted the alias `{factoid_name}`",
                channel=ctx.channel,
            )
            return

        # -- Handling for parents --

        # Gets list of aliases
        aliases = (
            await self.bot.models.Factoid.query.where(
                self.bot.models.Factoid.alias == factoid_name
            )
            .where(self.bot.models.Factoid.guild == str(ctx.guild.id))
            .gino.all()
        )
        # Stop execution if there is no other parent to be assigned
        if len(aliases) == 0:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` has no aliases.", channel=ctx.channel
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
                message=f"I couldn't find the new parent `{replacement_name}`"
                + ", picking new parent at random",
                channel=ctx.channel,
            )

        new_entry = await self.get_raw_factoid_entry(new_name, str(ctx.guild.id))
        new_entry.name = new_name
        new_entry.message = factoid.message
        new_entry.embed_config = factoid.embed_config
        new_entry.alias = None
        await self.modify_factoid_call(factoid=new_entry)

        # Updates old aliases
        await self.handle_parent_change(ctx, aliases, new_name)
        await auxiliary.send_confirm_embed(
            message=f"Deleted the alias `{factoid_name}`",
            channel=ctx.channel,
        )

        # Logs the new parent change
        config = self.bot.guild_configs[str(ctx.guild.id)]
        log_channel = config.get("logging_channel")
        await self.bot.logger.send_log(
            message=(
                f"Factoid dealias: Deleted the alias `{factoid_name}`, new"
                f" parent: `{new_name}`"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=ctx.guild, channel=ctx.channel),
            channel=log_channel,
        )

        jobs = (
            await self.bot.models.FactoidJob.query.where(
                self.bot.models.Factoid.guild == factoid.guild
            )
            .where(self.bot.models.Factoid.factoid_id == factoid.factoid_id)
            .gino.all()
        )
        # Deletes the factoid and deletes all jobs tied to it
        await self.delete_factoid_call(factoid, str(ctx.guild.id))

        # If there were jobs tied to it, recreate them with the new factoid
        if jobs:
            for job in jobs:
                new_job = self.bot.models.FactoidJob(
                    factoid=new_entry.factoid_id, channel=job.channel, cron=job.cron
                )
                await new_job.create()

                job_id = new_job.job_id
                self.running_jobs[job_id] = {}
                self.running_jobs[job_id]["job"] = new_job

                # Starts the new job
                task = asyncio.create_task(self.cronjob(new_job, ctx))
                self.running_jobs[job_id]["task"] = task

    @auxiliary.with_typing
    @commands.has_permissions(administrator=True)
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Flushes all factoid caches",
        description="Flushes all factoid caches",
    )
    async def flush(self, ctx: commands.Context):
        """Command to flush all factoid caches

        Args:
            ctx (commands.Context): Context of the invokation
        """
        self.factoid_cache.clear()  # Factoid execution cache
        self.factoid_all_cache.clear()  # Factoid all URL cache

        await auxiliary.send_confirm_embed(
            message=f"Factoid caches for `{str(ctx.guild.id)}` succesfully flushed!",
            channel=ctx.channel,
        )

    # -- Property Commands --

    # Hiding

    @auxiliary.with_typing
    @commands.check(has_admin_factoids_role)
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

        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        if factoid.hidden:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is already hidden",
                channel=ctx.channel,
            )
            return
        factoid.hidden = True
        await self.modify_factoid_call(factoid=factoid)

        await auxiliary.send_confirm_embed(
            message=f"`{factoid_name}` is now hidden", channel=ctx.channel
        )

    @auxiliary.with_typing
    @commands.check(has_admin_factoids_role)
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
        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        if not factoid.hidden:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is already unhidden",
                channel=ctx.channel,
            )
            return

        factoid.hidden = False
        await self.modify_factoid_call(factoid=factoid)

        await auxiliary.send_confirm_embed(
            message=f"`{factoid_name}` is now unhidden", channel=ctx.channel
        )

    # Protecting

    @auxiliary.with_typing
    @commands.check(has_admin_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Protects a factoid",
        description="Protects a factoid and prevents modification or deletion",
        usage="[factoid-name]",
    )
    async def protect(
        self,
        ctx: commands.Context,
        factoid_name: str,
    ):
        """Command to protect a factoid from being deleted or modified

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): Name of the factoid to hide
        """

        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is already protected",
                channel=ctx.channel,
            )
            return
        factoid.protected = True
        await self.modify_factoid_call(factoid=factoid)

        await auxiliary.send_confirm_embed(
            message=f"`{factoid_name}` is now protected", channel=ctx.channel
        )

    @auxiliary.with_typing
    @commands.check(has_admin_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Unprotects a factoid",
        description="Allows a protected factoid to be modified or deleted",
        usage="[factoid-name]",
    )
    async def unprotect(
        self,
        ctx: commands.Context,
        factoid_name: str,
    ):
        """Command to unprotect a factoid and allow it to be deleted or modified

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): The name of the factoid to unhide
        """
        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        factoid.protected = False
        await self.modify_factoid_call(factoid=factoid)

        await auxiliary.send_confirm_embed(
            message=f"`{factoid_name}` is now unprotected", channel=ctx.channel
        )

    # Restricting

    @auxiliary.with_typing
    @commands.check(has_admin_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Restricts a factoid",
        description="Restricts a factoid and only allows it to be called in certain channels",
        usage="[factoid-name]",
    )
    async def restrict(
        self,
        ctx: commands.Context,
        factoid_name: str,
    ):
        """Command to restrict a factoid to only certain channels

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): Name of the factoid to hide
        """

        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        if factoid.restricted:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is already restricted",
                channel=ctx.channel,
            )
            return
        factoid.restricted = True
        await self.modify_factoid_call(factoid=factoid)

        await auxiliary.send_confirm_embed(
            message=f"`{factoid_name}` is now restricted", channel=ctx.channel
        )

    @auxiliary.with_typing
    @commands.check(has_admin_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Unrestricts a factoid",
        description="Unrestricts a factoid and allows it to be called anywhere",
        usage="[factoid-name]",
    )
    async def unrestrict(
        self,
        ctx: commands.Context,
        factoid_name: str,
    ):
        """Command to allow a factoid to be called anywhere

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): The name of the factoid to unhide
        """
        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        if not factoid.restricted:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is already unrestricted",
                channel=ctx.channel,
            )
            return

        factoid.restricted = False
        await self.modify_factoid_call(factoid=factoid)

        await auxiliary.send_confirm_embed(
            message=f"`{factoid_name}` is now unrestricted", channel=ctx.channel
        )

    # Disabling

    @auxiliary.with_typing
    @commands.check(has_admin_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Disables a factoid",
        description="Disables a factoid and prevents it from being called anywhere",
        usage="[factoid-name]",
    )
    async def disable(
        self,
        ctx: commands.Context,
        factoid_name: str,
    ):
        """Command to completely prevent a factoid from being called

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): Name of the factoid to hide
        """

        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        if factoid.disabled:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is already disabled",
                channel=ctx.channel,
            )
            return
        factoid.disabled = True
        await self.modify_factoid_call(factoid=factoid)

        await auxiliary.send_confirm_embed(
            message=f"`{factoid_name}` is now disabled", channel=ctx.channel
        )

    @auxiliary.with_typing
    @commands.check(has_admin_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Enables a factoid",
        description="Enables a factoid and allows it to be called",
        usage="[factoid-name]",
    )
    async def enable(
        self,
        ctx: commands.Context,
        factoid_name: str,
    ):
        """Command to allow a factoid to be called

        Args:
            ctx (commands.Context): Context of the invokation
            factoid_name (str): The name of the factoid to unhide
        """
        factoid = await self.get_factoid(factoid_name, str(ctx.guild.id))

        if factoid.protected:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is protected and cannot be modified",
                channel=ctx.channel,
            )
            return

        if not factoid.disabled:
            await auxiliary.send_deny_embed(
                message=f"`{factoid_name}` is already enabled",
                channel=ctx.channel,
            )
            return

        factoid.disabled = False
        await self.modify_factoid_call(factoid=factoid)

        await auxiliary.send_confirm_embed(
            message=f"`{factoid_name}` is now enabled", channel=ctx.channel
        )
