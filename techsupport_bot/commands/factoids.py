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
from enum import Enum
from socket import gaierror
from typing import TYPE_CHECKING, Self

import aiocron
import discord
import expiringdict
import munch
import ui
import yaml
from aiohttp.client_exceptions import InvalidURL
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs, custom_errors, extensionconfig
from croniter import CroniterBadCronError
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Factoid plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
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
    config.add(
        key="disable_embeds",
        datatype="bool",
        title="Force disable embeds, for debug purposes",
        description="This will force all factoids to not use embeds.",
        default=False,
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
        ctx.guild, ctx.author, config.extensions.factoids.manage_roles.value
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
        ctx.guild, ctx.author, config.extensions.factoids.admin_roles.value
    )


async def has_given_factoids_role(
    guild: discord.Guild, invoker: discord.Member, check_roles: list[str]
) -> bool:
    """-COMMAND CHECK-
    Checks if the invoker has a factoid management role

    Args:
        guild (discord.Guild): The guild the factoids command was called in
        invoker (discord.Member): This is the member who called the factoids command
        check_roles (list[str]): The list of string names of roles

    Raises:
        CommandError: No management roles assigned in the config
        MissingAnyRole: Invoker doesn't have a factoid management role

    Returns:
        bool: Whether the invoker has a factoid management role
    """
    factoid_roles = []
    # Gets permitted roles
    for name in check_roles:
        factoid_role = discord.utils.get(guild.roles, name=name)
        if not factoid_role:
            continue
        factoid_roles.append(factoid_role)

    if not factoid_roles:
        raise commands.CommandError(
            "No factoid management roles found in the config file"
        )
    # Checking against the user to see if they have the roles specified in the config
    if not any(
        factoid_role in getattr(invoker, "roles", []) for factoid_role in factoid_roles
    ):
        raise commands.MissingAnyRole(factoid_roles)

    return True


@dataclass
class CalledFactoid:
    """A class to allow keeping the original factoid name in tact
    Without having to call the database lookup function every time

    Attributes:
        original_call_str (str): The original name the user provided for a factoid
        factoid_db_entry (bot.models.Factoid): The database entry for the original factoid
    """

    original_call_str: str
    factoid_db_entry: bot.models.Factoid


class Properties(Enum):
    """
    This enum is for the new factoid all to be able to handle dynamic properties

    Attributes:
        HIDDEN (str): Representation of hidden
        DISABLED (str): Representation of disabled
        RESTRICTED (str): Representation of restricted
        PROTECTED (str): Representation of protected
    """

    HIDDEN: str = "hidden"
    DISABLED: str = "disabled"
    RESTRICTED: str = "restricted"
    PROTECTED: str = "protected"


class FactoidManager(cogs.MatchCog):
    """
    Manages all factoid features

    Attributes:
        CRON_REGEX (str): The regex to check if a cronjob is correct
        factoid_app_group (app_commands.Group): Group for /factoid commands
    """

    CRON_REGEX: str = (
        r"^((\*|([0-5]?\d|\*\/\d+)(-([0-5]?\d))?)(,\s*(\*|([0-5]?\d|\*\/\d+)(-([0-5]"
        + r"?\d))?)){0,59}\s+){4}(\*|([0-7]?\d|\*(\/[1-9]|[1-5]\d)|mon|tue|wed|thu|fri|sat|sun"
        + r")|\*\/[1-9])$"
    )

    factoid_app_group: app_commands.Group = app_commands.Group(
        name="factoid", description="Command Group for the Factoids Extension"
    )

    async def preconfig(self: Self) -> None:
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
    async def delete_factoid_call(
        self: Self, factoid: bot.models.Factoid, guild: str
    ) -> None:
        """Calls the db to delete a factoid

        Args:
            factoid (bot.models.Factoid): The factoid to delete
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
        self: Self,
        factoid_name: str,
        guild: str,
        message: str,
        embed_config: str,
        alias: str = None,
    ) -> None:
        """Calls the DB to create a factoid

        Args:
            factoid_name (str): The name of the factoid
            guild (str): Guild of the factoid
            message (str): Message the factoid should send
            embed_config (str): Whether the factoid has an embed set up
            alias (str, optional): The parent factoid. Defaults to None.

        Raises:
            TooLongFactoidMessageError:
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
        self: Self,
        factoid: bot.models.Factoid,
    ) -> None:
        """Makes a DB call to modify a factoid

        Args:
            factoid (bot.models.Factoid): Factoid to modify.

        Raises:
            TooLongFactoidMessageError:
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
        self: Self, factoid_name: str, ctx: commands.Context, fmt: str
    ) -> bool:
        """Confirms if a factoid should be deleted/modified

        Args:
            factoid_name (str): The factoid that is being prompted for deletion
            ctx (commands.Context): Used to return the message
            fmt (str): Formatting for the returned message

        Returns:
            bool: Whether the factoid was deleted/modified
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
        self: Self, ctx: commands.Context, factoid_name: str, message: str
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
        self: Self, ctx: commands.Context, aliases: list, new_name: str
    ) -> None:
        """Changes the list of aliases to point to a new name

        Args:
            ctx (commands.Context): Used for cache handling
            aliases (list): A list of aliases to change
            new_name (str): The name of the new parent
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
        self: Self,
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

    def get_embed_from_factoid(
        self: Self, factoid: bot.models.Factoid
    ) -> discord.Embed:
        """Gets the factoid embed from its message.

        Args:
            factoid (bot.models.Factoid): The factoid to get the json of

        Returns:
            discord.Embed: The embed of the factoid
        """
        if not factoid.embed_config:
            return None

        embed_config = json.loads(factoid.embed_config)

        return discord.Embed.from_dict(embed_config)

    # -- Cache functions --
    async def handle_cache(self: Self, guild: str, factoid_name: str) -> None:
        """Deletes factoid from the factoid cache

        Args:
            guild (str): The guild to get the cache key
            factoid_name (str): The name of the factoid to remove from the cache
        """
        key = self.get_cache_key(guild, factoid_name)

        if key in self.factoid_cache:
            del self.factoid_cache[key]

    def get_cache_key(self: Self, guild: str, factoid_name: str) -> str:
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
        self: Self, guild: str = None, list_hidden: bool = False
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

    async def get_raw_factoid_entry(
        self: Self, factoid_name: str, guild: str
    ) -> bot.models.Factoid:
        """Searches the db for a factoid by its name, does NOT follow aliases

        Args:
            factoid_name (str): The name of the factoid to get
            guild (str): The id of the guild for the factoid

        Raises:
            FactoidNotFoundError: Raised when the provided factoid doesn't exist

        Returns:
            bot.models.Factoid: The factoid
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

    async def get_factoid(
        self: Self, factoid_name: str, guild: str
    ) -> bot.models.Factoid:
        """Gets the factoid from the DB, follows aliases

        Args:
            factoid_name (str): The name of the factoid to get
            guild (str): The id of the guild for the factoid

        Raises:
            FactoidNotFoundError: If the factoid wasn't found

        Returns:
            bot.models.Factoid: The factoid
        """
        factoid = await self.get_raw_factoid_entry(factoid_name, guild)

        # Handling if the call is an alias
        if factoid and factoid.alias not in ["", None]:
            factoid = await self.get_raw_factoid_entry(factoid.alias, guild)
            factoid_name = factoid.name

        if not factoid:
            raise custom_errors.FactoidNotFoundError(factoid=factoid_name)

        return factoid

    async def get_list_of_aliases(
        self: Self, factoid_to_search: str, guild: str
    ) -> list[str]:
        """Gets an alphabetical list of all ways to call a factoid
        This will include the internal parent AND all aliases

        Args:
            factoid_to_search (str): The name of the factoid to search for aliases of
            guild (str): The guild to search for factoids in

        Returns:
            list[str]: The list of all ways to call the factoid, including what was passed
        """
        factoid = await self.get_factoid(factoid_to_search, guild)
        alias_list = [factoid.name]
        factoids = await self.get_all_factoids(guild)
        for test_factoid in factoids:
            if test_factoid.alias and test_factoid.alias == factoid.name:
                alias_list.append(test_factoid.name)
        return sorted(alias_list)

    # -- Adding and removing factoids --

    async def add_factoid(
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
        guild: str,
        message: str,
        embed_config: str,
        alias: str = None,
    ) -> None:
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
        self: Self, ctx: commands.Context, called_factoid: CalledFactoid
    ) -> bool:
        """Deletes a factoid with confirmation

        Args:
            ctx (commands.Context): Context to send the confirmation message to
            called_factoid (CalledFactoid): The factoid to remove

        Returns:
            bool: Whether the factoid was deleted
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
    async def match(
        self: Self, config: munch.Munch, _: commands.Context, message_contents: str
    ) -> bool:
        """Checks if a message started with the prefix from the config

        Args:
            config (munch.Munch): The config to get the prefix from
            message_contents (str): The message to check

        Returns:
            bool: Whether the message starts with the prefix or not
        """
        return message_contents.startswith(config.extensions.factoids.prefix.value)

    async def response(
        self: Self,
        config: munch.Munch,
        ctx: commands.Context,
        message_content: str,
        _: bool,
    ) -> None:
        """Responds to a factoid call

        Args:
            config (munch.Munch): The server config
            ctx (commands.Context): Context of the call
            message_content (str): Content of the call

        Raises:
            TooLongFactoidMessageError:
                Raised when the raw message content is over discords 2000 char limit
        """
        if not ctx.guild:
            return
        # Checks if the first word of the content after the prefix is a valid factoid
        # Replaces \n with spaces so factoid can be called even with newlines
        prefix = config.extensions.factoids.prefix.value
        query = message_content[len(prefix) :].replace("\n", " ").split(" ")[0].lower()
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
        if not config.extensions.factoids.disable_embeds.value:
            embed = self.get_embed_from_factoid(factoid)
        else:
            embed = None
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
        self: Self,
        channel: discord.abc.Messageable,
        message: discord.Message,
        factoid_message: str,
    ) -> None:
        """Send a factoid to IRC channel, if it was called in a linked channel

        Args:
            channel (discord.abc.Messageable): The channel the factoid was sent in
            message (discord.Message): The message object of the invocation
            factoid_message (str): The text of the factoid to send
        """
        # Don't attempt to send a message if irc if irc is disabled
        irc_config = self.bot.file_config.api.irc
        if not irc_config.enable_irc:
            return

        await self.bot.irc.irc_cog.handle_factoid(
            channel=channel,
            discord_message=message,
            factoid_message=factoid_message,
        )

    # -- Factoid job related functions --
    async def kickoff_jobs(self: Self) -> None:
        """Gets a list of cron jobs and starts them"""
        jobs = await self.bot.models.FactoidJob.query.gino.all()
        for job in jobs:
            job_id = job.job_id
            self.running_jobs[job_id] = {}

            # This allows the task to be manually cancelled, preventing one more execution
            task = asyncio.create_task(self.cronjob(job))
            task = self.running_jobs[job_id]["task"] = task

    async def cronjob(
        self: Self, job: bot.models.FactoidJob, ctx: commands.Context = None
    ) -> None:
        """Run a cron job for a factoid

        Args:
            job (bot.models.FactoidJob): The job to start
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
                    channel = None

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

            config = self.bot.guild_configs[str(channel.guild.id)]

            # Checking for disabled or restricted
            if factoid.disabled:
                return

            if (
                factoid.restricted
                and str(channel.id)
                not in config.extensions.factoids.restricted_list.value
            ):
                return

            # Get_embed accepts job as a factoid object
            if not config.extensions.factoids.disable_embeds.value:
                embed = self.get_embed_from_factoid(factoid)
            else:
                embed = None

            try:
                content = factoid.message if not embed else None
            except ValueError:
                # The not embed causes a ValueError in certian places. This ensures fallback works
                content = factoid.message

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
    async def factoid(self: Self, ctx: commands.Context) -> None:
        """The bare .factoid command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

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
        self: Self, ctx: commands.Context, factoid_name: str, *, message: str = ""
    ) -> None:
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
    async def forget(self: Self, ctx: commands.Context, factoid_name: str) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
        channel: discord.TextChannel,
        *,
        cron_config: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
        channel: discord.TextChannel,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
        channel: discord.TextChannel,
    ) -> None:
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
    async def jobs(self: Self, ctx: commands.Context) -> None:
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
    async def _json(self: Self, ctx: commands.Context, factoid_name: str) -> None:
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
        self: Self,
        ctx: commands.Context,
        query: str,
    ) -> None:
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

    @factoid_app_group.command(
        name="all",
        description="Sends a configurable list of all factoids.",
        extras={
            "brief": "Sets a note for a user",
            "usage": "[file] [property] [true_all] [ignore_hidden]",
            "module": "factoids",
        },
    )
    async def app_command_all(
        self: Self,
        interaction: discord.Interaction,
        force_file: bool = False,
        property: Properties = "",
        true_all: bool = False,
        show_hidden: bool = False,
    ) -> None:
        """This is the more feature full version of factoid all
        This is an application command

        Args:
            interaction (discord.Interaction): The interaction that started this command
            force_file (bool, optional): Whether this should be forced as a yml file.
                Defaults to False.
            property (Properties, optional): What property to look for. Defaults to "".
            true_all (bool, optional): Whether this should force every factoid. Defaults to False.
            show_hidden (bool, optional): If set to true will show hidden factoids.
                Defaults to False.
        """
        guild = str(interaction.guild.id)
        # Check for admin roles if ignoring hidden
        if true_all or show_hidden:
            config = self.bot.guild_configs[str(interaction.guild.id)]
            await has_given_factoids_role(
                interaction.guild,
                interaction.user,
                config.extensions.factoids.admin_roles.value,
            )

        if true_all:
            factoids = await self.build_list_of_factoids(guild, include_hidden=True)
        else:
            factoids = await self.build_list_of_factoids(
                guild, exclusive_property=property, include_hidden=show_hidden
            )

        aliases = self.build_alias_dict_for_given_factoids(factoids)

        # If the linx server isn't configured, we must make it a file
        if not self.bot.file_config.api.api_url.linx:
            force_file = True

        cachable = bool(
            not force_file and not property and not true_all and not show_hidden
        )

        if cachable and guild in self.factoid_all_cache:
            url = self.factoid_all_cache[guild]["url"]
            embed = auxiliary.prepare_confirm_embed(url)
            await interaction.response.send_message(embed=embed)
            return

        factoid_all = await self.build_factoid_all(
            interaction.guild, factoids, aliases, force_file, cachable
        )

        if not factoid_all:
            embed = auxiliary.prepare_deny_embed(
                "No factoids could be found matching your filter"
            )
            await interaction.response.send_message(embed=embed)
            return

        # If we know it's a file, or it's fallen back to a file, send it as a file
        if force_file or isinstance(factoid_all, discord.File):
            await interaction.response.send_message(file=factoid_all)
            return

        embed = auxiliary.prepare_confirm_embed(factoid_all)
        await interaction.response.send_message(embed=embed)

    async def build_list_of_factoids(
        self: Self,
        guild: discord.Guild,
        exclusive_property: Properties = "",
        include_hidden: bool = False,
    ) -> list[munch.Munch]:
        """This builds a list of database objects that match the factoid all requests

        Args:
            guild (discord.Guild): The guild to pull factoids from
            exclusive_property (Properties, optional): What property to exclusivly get.
                Defaults to "".
            include_hidden (bool, optional): Whether this query should ignore the hidden property.
                Defaults to False.

        Returns:
            list[munch.Munch]: The filtered list of factoids
        """
        factoids = await self.get_all_factoids(guild, list_hidden=True)
        # If there are no factoids for the guild, return None
        if not factoids:
            return None
        # If exclusive property is set, then that property as the only one
        # This obeys include_hidden
        if exclusive_property:
            filtered_factoids = [
                factoid
                for factoid in factoids
                if getattr(factoid, exclusive_property.value)
                and (include_hidden or not factoid.hidden)
            ]
            return filtered_factoids
        # If no specific property is set, see if we have to filter out hidden factoids
        if not include_hidden:
            filtered_factoids = [factoid for factoid in factoids if not factoid.hidden]
            return filtered_factoids
        # Otherwise just return every factoid
        return factoids

    def build_alias_dict_for_given_factoids(
        self: Self, factoids: list[munch.Munch]
    ) -> dict[str, list[str]]:
        """This builds a dict of parent to aliases for a given list of factoids

        Args:
            factoids (list[munch.Munch]): The factoid list to find aliases for

        Returns:
            dict[str, list[str]]: The dict of parent to list of aliases
        """
        aliases = {}
        for factoid in factoids:
            if factoid.alias not in [None, ""]:
                # Append to aliases
                if factoid.alias in aliases:
                    aliases[factoid.alias].append(factoid.name)
                    continue

                aliases[factoid.alias] = [factoid.name]
        return aliases

    async def build_factoid_all(
        self: Self,
        guild: discord.Guild,
        factoids: list[munch.Munch],
        aliases: dict[str, list[str]],
        use_file: bool,
        cachable: bool,
    ) -> discord.File | str:
        """This builds the factoid all url or the yaml file

        Args:
            guild (discord.Guild): The guild to build factoid all for
            factoids (list[munch.Munch]): The factoids to include in the all
            aliases (dict[str, list[str]]): Aliases for the given factoids
            use_file (bool): Whether to force the use of a file or not
            cachable (bool): Whether this request is cachable

        Returns:
            discord.File | str: The final formatted factoid all
        """

        if use_file:
            return await self.send_factoids_as_file(guild, factoids, aliases)

        try:
            # -Tries calling the api-
            html = await self.generate_html(guild, factoids, aliases)
            # If there are no applicable factoids
            if html is None:
                # Something must go wrong to get here
                return None

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

            if cachable:
                self.factoid_all_cache[str(guild.id)] = {}
                self.factoid_all_cache[str(guild.id)]["url"] = url

            return url

        # If an error happened while calling the api
        except (gaierror, InvalidURL) as exception:
            config = self.bot.guild_configs[str(guild.id)]
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message="Could not render/send all-factoid HTML",
                level=LogLevel.ERROR,
                context=LogContext(guild=guild),
                channel=log_channel,
                exception=exception,
            )

            return await self.send_factoids_as_file(guild, factoids, aliases)

    def build_formatted_factoid_data(
        self: Self, factoids: list[munch.Munch], aliases: dict[str, list[str]]
    ) -> dict[str, dict[str, str]]:
        """This builds a nicely formatted, sorted, and processed dict of factoids
        Ready to be put into factoid all

        Args:
            factoids (list[munch.Munch]): The list of all parent factoids to be included
            aliases (dict[str, list[str]]): The list of all aliases, if any,
                for the factoids in the main factoids list

        Returns:
            dict[str, dict[str, str]]: The formatted list of factoids with all the information
        """
        output_data = []
        for factoid in factoids:
            # Skips aliases
            if factoid.alias not in [None, ""]:
                continue

            # Default name to the actual factoid name
            name = factoid.name

            # If not aliased
            if factoid.name in aliases:
                all_aliases = [factoid.name] + aliases[factoid.name]
                all_aliases.sort()
                name = all_aliases[0]
                data = {
                    "message": factoid.message,
                    "embed": bool(factoid.embed_config),
                    "aliases": all_aliases[1:],
                }

            # If aliased
            else:
                data = {"message": factoid.message, "embed": bool(factoid.embed_config)}

            output_data.append({name: data})

        # Sort output alphabetically
        output_data = sorted(output_data, key=lambda x: list(x.keys())[0])
        return output_data

    async def generate_html(
        self: Self,
        guild: discord.Guild,
        factoids: list[munch.Munch],
        aliases: dict[str, list[str]],
    ) -> str:
        """Method to generate the html file contents

        Args:
            guild (discord.Guild): The guild the factoids are being pulled from
            factoids (list[munch.Munch]): List of all factoids
            aliases (dict[str, list[str]]): A dictionary containing factoids and their aliases

        Returns:
            str: The result html file
        """

        body_contents = ""

        output_data = self.build_formatted_factoid_data(factoids, aliases)

        if not output_data:
            # Something is wrong with the database if we are ever here
            return None

        for factoid in output_data:
            name, data = next(iter(factoid.items()))
            embed_text = " (embed)" if data["embed"] else ""

            if "aliases" in data:
                body_contents += (
                    f"<li><code>{name} [{', '.join(data['aliases'])}]{embed_text}"
                    + f" - {data['message']}</code></li>"
                )
            else:
                body_contents += (
                    f"<li><code>{name}{embed_text}"
                    + f" - {data['message']}</code></li>"
                )

        if body_contents == "":
            return None

        body_contents = f"<ul>{body_contents}</ul>"
        output = (
            f"""
        <!DOCTYPE html>
        <html>
        <body>
        <h3>Factoids for {guild.name}</h3>
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
        self: Self,
        guild: discord.Guild,
        factoids: list[munch.Munch],
        aliases: dict[str, list[str]],
    ) -> discord.File:
        """Method to send the factoid list as a file instead of a paste

        Args:
            guild (discord.Guild): The guild the factoids are from
            factoids (list[munch.Munch]): List of all factoids
            aliases (dict[str, list[str]]): A dictionary containing factoids and their aliases

        Returns:
            discord.File: The file, ready to upload to discord
        """

        output_data = self.build_formatted_factoid_data(factoids, aliases)

        if not output_data:
            # Something is wrong with the database if we are ever here
            return None

        yaml_file = discord.File(
            io.StringIO(yaml.dump(output_data)),
            filename=(
                f"factoids-for-server-{guild.id}-{datetime.datetime.utcnow()}.yaml"
            ),
        )

        # Returns the file
        return yaml_file

    def search_content_and_bold(
        self: Self, original: str, search_string: str
    ) -> list[str]:
        """Searches a string for a substring and bolds it

        Args:
            original (str): The original content to search through
            search_string (str): The string we are searching for

        Returns:
            list[str]: Snippets that have been modified with the search string
        """
        # Compile the regular expression for the substring
        pattern = re.compile(re.escape(search_string))
        matches = list(pattern.finditer(original))

        matches_list = []

        # Print all instances with 20 characters before and after each occurrence
        for match in matches:
            start = max(match.start() - 20, 0)
            end = min(match.end() + 20, len(original))
            context = original[start:end]
            # Replace the substring in the context with the formatted version
            context_with_formatting = context.replace(
                search_string, f"**{search_string}**"
            )
            matches_list.append(context_with_formatting.replace("****", ""))

        return matches_list

    @auxiliary.with_typing
    @commands.guild_only()
    @factoid.command(
        aliases=["find"],
        brief="Searches a factoid",
        description="Searches a factoid by name and contents",
        usage="[search-query]",
    )
    async def search(self: Self, ctx: commands.Context, *, query: str) -> None:
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
        matches = {}

        for factoid in factoids:
            factoid_key = ", ".join(await self.get_list_of_aliases(factoid.name, guild))
            if query in factoid.name.lower():
                if factoid_key in matches:
                    matches[factoid_key].append(
                        f"Name: {factoid.name.lower().replace(query, f'**{query}**')}"
                    )
                else:
                    matches[factoid_key] = [
                        f"Name: {factoid.name.lower().replace(query, f'**{query}**')}"
                    ]

            if query in factoid.message.lower():
                matches_list = self.search_content_and_bold(
                    factoid.message.lower(), query
                )
                for match in matches_list:
                    if factoid_key in matches:
                        matches[factoid_key].append(f"Content: {match}")
                    else:
                        matches[factoid_key] = [f"Content: {match}"]

            if (
                factoid.embed_config is not None
                and query in factoid.embed_config.lower()
            ):
                matches_list = self.search_content_and_bold(
                    factoid.embed_config.lower(), query
                )
                for match in matches_list:
                    if factoid_key in matches:
                        matches[factoid_key].append(
                            f"Embed: {match.replace('_', '`_`')}"
                        )
                    else:
                        matches[factoid_key] = [f"Embed: {match.replace('_', '`_`')}"]
        if len(matches) == 0:
            embed = auxiliary.prepare_deny_embed(
                f"No factoids could be found matching `{query}`"
            )
            await ctx.send(embed=embed)
            return
        embeds = []
        embed = discord.Embed(color=discord.Color.green())
        for index, match in enumerate(matches):
            if index > 0 and index % 10 == 0:
                embeds.append(embed)
                embed = discord.Embed(color=discord.Color.green())
            embed.add_field(name=match, value="\n".join(matches.get(match)))

        embeds.append(embed)
        await ui.PaginateView().send(ctx.channel, ctx.author, embeds)

    @auxiliary.with_typing
    @commands.check(has_manage_factoids_role)
    @commands.guild_only()
    @factoid.command(
        brief="Adds a factoid alias",
        description="Adds an alternate way to call a factoid",
        usage="[new-alias-name] [original-factoid-name]",
    )
    async def alias(
        self: Self,
        ctx: commands.Context,
        alias_name: str,
        factoid_name: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
        replacement_name: str = None,
    ) -> None:
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
    async def flush(self: Self, ctx: commands.Context) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
    ) -> None:
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
        self: Self,
        ctx: commands.Context,
        factoid_name: str,
    ) -> None:
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
