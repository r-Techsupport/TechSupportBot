from __future__ import annotations

import asyncio
import datetime
import hashlib
import io
import json
import re
from dataclasses import dataclass
from enum import IntFlag
from socket import gaierror
from typing import TYPE_CHECKING, Self
from urllib.parse import urlsplit, urlunsplit

import discord
import expiringdict
import yaml
from aiohttp.client_exceptions import InvalidURL
from apscheduler.triggers.cron import CronTrigger
from discord import app_commands

import configuration
import ui
from botlogging import LogContext, LogLevel
from core import auxiliary, cogs
from modules.moderation import logger as function_logger

if TYPE_CHECKING:
    import bot


async def has_manage_factoids_role(
    interaction: discord.Interaction,
) -> bool:
    """A command check to determine if the invoker has a configured manage role

    Args:
        interaction (discord.Interaction): The context the command was run

    Returns:
        bool: True if the command can be run, False if it can't
    """
    return await has_given_factoids_role(
        interaction.guild,
        interaction.user,
        configuration.get_config_entry(interaction.guild.id, "factoids_manage_roles"),
    )


async def has_admin_factoids_role(interaction: discord.Interaction) -> bool:
    """A command check to determine if the invoker has a configured admin role

    Args:
       interaction (discord.Interaction): The context the command was run

    Returns:
        bool: True if the command can be run, False if it can't
    """
    return await has_given_factoids_role(
        interaction.guild,
        interaction.user,
        configuration.get_config_entry(interaction.guild.id, "factoids_admin_roles"),
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
        AppCommandError: No management roles assigned in the config
        MissingAnyRole: Invoker doesn't have a factoid management role

    Returns:
        bool: Whether the invoker has a factoid management role
    """
    factoid_roles = []
    # Gets permitted roles
    for id in check_roles:
        factoid_role = guild.get_role(int(id))
        if not factoid_role:
            continue
        factoid_roles.append(factoid_role)

    if not factoid_roles:
        raise app_commands.AppCommandError(
            "No factoid management roles found in the config file"
        )
    # Checking against the user to see if they have the roles specified in the config
    if not any(
        factoid_role in getattr(invoker, "roles", []) for factoid_role in factoid_roles
    ):
        raise app_commands.MissingAnyRole(factoid_roles)

    return True


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Factoid plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot to register the cog to
    """
    await bot.add_cog(FactoidManager(bot=bot))


@dataclass
class FactoidView:
    factoid_data_id: int
    message: str
    json_string: str
    flags: int
    times_called: int
    create_time: datetime.datetime
    edit_time: datetime.datetime
    calls: list[str]


class Properties(IntFlag):
    """
    This enum is for the new factoid all to be able to handle dynamic properties

    Attributes:
        DISABLED (int): Representation of disabled
        HIDDEN (int): Representation of hidden
        PROTECTED (int): Representation of protected
        RESTRICTED (int): Representation of restricted
    """

    DISABLED: int = 0b1000
    HIDDEN: int = 0b0100
    PROTECTED: int = 0b0010
    RESTRICTED: int = 0b0001


# TODO: Race condition limiting effects on /factoid edit
# TODO: Warning on body/embed contents with discord CDN links
# TODO: Update/remake all doc strings
# TODO: Make a cleanup command to purge and hanging database entries. Data without any calls, calls/jobs pointing to missing data entries
class FactoidManager(cogs.BaseCog):

    factoid_app_group: app_commands.Group = app_commands.Group(
        name="factoid",
        description="Commands to create, manage and use the factoids system",
    )

    factoid_loop_commands: app_commands.Group = app_commands.Group(
        name="loop",
        description="Commands to create, view and manage the factoid loops system",
        parent=factoid_app_group,
    )

    # PRECONFIG

    async def preconfig(self: Self) -> None:
        """This sets up cache and job loop calls"""
        self.factoid_cache = expiringdict.ExpiringDict(
            max_len=500,
            max_age_seconds=82800,
        )

        # Factoid all cache setup to save links for 23 hours, to avoid links that are close to expiring from being presented
        self.factoid_all_cache = expiringdict.ExpiringDict(
            max_len=50,
            max_age_seconds=82800,
        )

        # Autocomplete cache to avoid constant DB calls
        # guild ID: list[(name, flags)]
        self.factoid_autocomplete_cache: dict[int, list[tuple[str, int]]] = {}

        # Register the loop callback into APScheduler
        self.bot.scheduler.register_task(
            "factoid_loop",
            self.execute_job,
        )

        # On bot startup, start all jobs
        await self.startup_jobs()

    # LOOP STUFF

    async def startup_jobs(self: Self) -> None:
        all_jobs = await self.bot.models.FactoidJob.query.gino.all()
        for job in all_jobs:
            await self.register_job(job)

    async def register_job(self: Self, job: bot.models.FactoidJob) -> None:
        guild = self.bot.get_guild(int(job.guild))
        await self.bot.scheduler.schedule_cron(
            task_name="factoid_loop",
            cron=job.cron,
            payload={"guild": guild, "job_id": job.factoid_job_id},
        )

    async def execute_job(
        self: Self,
        payload: dict,
    ) -> None:
        # Expand payload
        guild: discord.Guild = payload["guild"]
        factoid_job_id: int = payload["job_id"]
        job_data = await self.bot.models.FactoidJob.query.where(
            (self.bot.models.FactoidJob.guild == str(guild.id))
            & (self.bot.models.FactoidJob.factoid_job_id == factoid_job_id)
        ).gino.first()
        if not job_data:
            return
        factoid = await self.get_factoid_view_by_id(guild, job_data.factoid_data_id)
        if not factoid:
            return

        # If the FactoidJob and FactoidData entry both exist, the job is valid. We reschedule here to prevent a different error causing the job to be shadow cancelled
        await self.register_job(job_data)

        # If factoids has been disabled, don't execute the job
        # We have already rescheduled it, so it will check again later
        if not self.extension_enabled(guild=guild):
            return

        # If for some reason we cannot find the channel, don't bother trying to execute
        channel = self.bot.get_channel(int(job_data.channel))
        if not channel:
            return

        # Check if factoid is disabled. If so, don't send it
        if factoid.flags & Properties.DISABLED:
            return

        # Check if factoid is restricted. If so, check if we can call it
        if (
            factoid.flags & Properties.RESTRICTED
            and not self.can_channel_send_restricted(channel)
        ):
            return

        embed, plaintext_content = await self.generate_sendable_factoid(guild, factoid)

        last_message = await channel.fetch_message(channel.last_message_id)
        embed_sent = False
        if embed:
            try:
                # If the bot wrote the last message, and its the same as the current job, do nothing
                if last_message.embeds:
                    old_embed_hash = self.compute_embed_hash(last_message.embeds[0])
                    new_embed_hash = self.compute_embed_hash(embed)
                    print(f"OLD: {old_embed_hash}, NEW: {new_embed_hash}")
                    if (
                        last_message.author == guild.me
                        and new_embed_hash == old_embed_hash
                    ):
                        return

                # Attempt to send the message with the embed in it
                sent_message = await channel.send(embed=embed)
                embed_sent = True
            # If something breaks, also log it
            except discord.errors.HTTPException as exception:
                asyncio.create_task(
                    self.log_embed_fallback_exception(
                        factoid=factoid,
                        exception=exception,
                        guild=guild,
                        channel=channel,
                    )
                )

        # Either no embed exists, or the embed failed to send for some reason.
        # We will send the plaintext content of the factoid in this case
        if not embed_sent:
            content = plaintext_content.strip()
            if len(content) > 2000:
                return

            # If the bot wrote the last message, and its the same as the current job, do nothing
            if last_message.author == guild.me and last_message.content == content:
                return

            sent_message = await channel.send(content=content)

        # Log in the background
        asyncio.create_task(
            self.log_factoid_send(
                guild=guild,
                channel=channel,
                sender=guild.me,
                factoid=factoid,
            )
        )

        # IRC connection
        self.send_factoid_to_irc(channel, factoid, guild.me)

        # Logger connection
        await self.send_factoid_to_logger(
            sent_message, guild.me, channel, factoid.message
        )

        # Increase times called
        await self.increment_times_called_by_view(guild=guild, factoid=factoid)

    async def unschedule_job(
        self: Self,
        job: bot.models.FactoidJob,
    ) -> None:
        """This removes the passed FactoidJob from the APScheduler queue

        Args:
            job (bot.models.FactoidJob): The job to remove from the queue
        """

        for scheduled_job in await self.bot.scheduler.get_upcoming_tasks():
            payload = scheduled_job["payload"]

            job_id = scheduled_job["job_id"]

            # Extract task name from APScheduler job ID
            task_name = job_id.split(":", 1)[0]

            # Ignore unrelated scheduled tasks
            if task_name != "factoid_loop":
                continue

            if (
                payload.get("job_id") == job.factoid_job_id
                and str(payload.get("guild").id) == job.guild
            ):
                self.bot.scheduler.scheduler.remove_job(job_id)

    # DATABASE CALLS

    async def create_factoid_call(
        self: Self,
        guild: discord.Guild,
        name: str,
        factoid_data_id: int,
    ) -> bot.models.FactoidCall:
        """This creates a new factoid call database entry for the given guild and factoid

        Args:
            self (Self): _description_
            guild (discord.Guild): The guild to create the factoid in
            name (str): The name of the factoid call to create
            factoid_data_id (int): The factoid data entry to associate this call with

        Returns:
            bot.models.FactoidCall: The newly created database entry
        """

        return await self.bot.models.FactoidCall.create(
            guild=str(guild.id),
            name=name,
            factoid_data_id=factoid_data_id,
        )

    async def read_factoid_call(
        self: Self,
        guild: discord.Guild,
        name: str,
    ) -> bot.models.FactoidCall:
        """Searches the database for a factoid call for the passed guild

        Args:
            guild (discord.Guild): The guild to find the factoid call of
            name (str): The name of the factoid to search for

        Returns:
            bot.models.FactoidCall: The database entry for the factoid call
        """

        return await self.bot.models.FactoidCall.query.where(
            (self.bot.models.FactoidCall.guild == str(guild.id))
            & (self.bot.models.FactoidCall.name == name)
        ).gino.first()

    async def read_factoid_data(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
    ) -> bot.models.FactoidData:
        """Searches the database for a factoid data for the passed guild

        Args:
            guild (discord.Guild): The guild to find the factoid data of
            factoid_data_id (int): The ID of the factoid to search for

        Returns:
            bot.models.FactoidData: The database entry for the factoid data
        """

        return await self.bot.models.FactoidData.query.where(
            (self.bot.models.FactoidData.guild == str(guild.id))
            & (self.bot.models.FactoidData.factoid_data_id == factoid_data_id)
        ).gino.first()

    async def update_factoid_data(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
        message: str = None,
        edit_time: datetime.datetime = None,
        flags: int = None,
        times_called: int = None,
        json_string: str = None,
    ) -> bot.models.FactoidData:
        """Partially updates a factoid data entry."""

        db_entry = await self.read_factoid_data(
            guild=guild,
            factoid_data_id=factoid_data_id,
        )

        update_values = {}

        if message is not None:
            update_values["message"] = message

        if edit_time is not None:
            update_values["edit_time"] = edit_time

        if flags is not None:
            update_values["flags"] = flags

        if times_called is not None:
            update_values["times_called"] = times_called

        if json_string is not None:
            update_values["json_string"] = json_string

        if update_values:
            await db_entry.update(**update_values).apply()

        return db_entry

    async def delete_factoid_call(
        self: Self,
        guild: discord.Guild,
        name: str,
    ) -> None:
        """Deletes a factoid call by name."""

        await self.bot.models.FactoidCall.delete.where(
            (self.bot.models.FactoidCall.guild == str(guild.id))
            & (self.bot.models.FactoidCall.name == name)
        ).gino.status()

    async def read_factoid_job_by_channel(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
        channel: discord.abc.GuildChannel,
    ) -> bot.models.FactoidJob:
        """Searches the database for a factoid job for the passed guild

        Args:
            guild (discord.Guild): The guild to find the factoid job of
            factoid_job_id (int): The ID of the factoid to search for

        Returns:
            bot.models.FactoidJob: The database entry for the factoid job
        """

        return await self.bot.models.FactoidJob.query.where(
            (self.bot.models.FactoidJob.guild == str(guild.id))
            & (self.bot.models.FactoidJob.factoid_data_id == factoid_data_id)
            & (self.bot.models.FactoidJob.channel == str(channel.id))
        ).gino.first()

    async def get_all_jobs_for_guild(
        self: Self, guild: discord.Guild
    ) -> list[bot.models.FactoidJob]:
        return await self.bot.models.FactoidJob.query.where(
            (self.bot.models.FactoidJob.guild == str(guild.id))
        ).gino.all()

    async def get_factoid_calls_by_factoid_id(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
    ) -> list[bot.models.FactoidCall]:
        """Returns all calls pointing to a factoid."""

        return await self.bot.models.FactoidCall.query.where(
            (self.bot.models.FactoidCall.guild == str(guild.id))
            & (self.bot.models.FactoidCall.factoid_data_id == factoid_data_id)
        ).gino.all()

    async def get_factoid_jobs_by_factoid_id(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
    ) -> list[bot.models.FactoidJob]:
        """Returns all jobs pointing to a factoid."""

        return await self.bot.models.FactoidJob.query.where(
            (self.bot.models.FactoidJob.guild == str(guild.id))
            & (self.bot.models.FactoidJob.factoid_data_id == factoid_data_id)
        ).gino.all()

    # DATABASE HELPERS

    async def get_factoid_view_by_name(
        self: Self,
        guild: discord.Guild,
        name: str,
    ) -> FactoidView | None:
        """Searches for the factoid associated with a given factoid name.

        Args:
            guild (discord.Guild): The guild to look for the factoid in
            name (str): The name of the factoid to lookup

        Returns:
            FactoidView | None: The factoid view, if found
        """

        call = await self.read_factoid_call(
            guild=guild,
            name=name,
        )

        if call is None:
            return None

        return await self.get_factoid_view_by_id(guild, call.factoid_data_id)

    async def get_factoid_view_by_id(
        self: Self, guild: discord.Guild, factoid_data_id: int
    ) -> FactoidView | None:
        cached_data = self.get_from_cache(guild, factoid_data_id)
        if cached_data:
            return cached_data

        factoid_data = await self.read_factoid_data(
            guild=guild,
            factoid_data_id=factoid_data_id,
        )

        if factoid_data is None:
            return None

        factoid_calls = await self.get_factoid_calls_by_factoid_id(
            guild=guild,
            factoid_data_id=factoid_data.factoid_data_id,
        )

        factoid = FactoidView(
            factoid_data_id=factoid_data.factoid_data_id,
            message=factoid_data.message,
            json_string=factoid_data.json_string,
            flags=factoid_data.flags,
            times_called=factoid_data.times_called,
            create_time=factoid_data.create_time,
            edit_time=factoid_data.edit_time,
            calls=sorted(factoid_call.name for factoid_call in factoid_calls),
        )

        self.add_to_cache(guild, factoid)

        return factoid

    async def delete_factoid_data_by_id(
        self: Self, guild: discord.Guild, id: int
    ) -> bool:
        """This deletes all FactoidData, FactoidCall and FactoidJob for the factoid ID passed

        Args:
            guild (discord.Guild): The guild the factoid to delete is in
            id (int): The ID of the factoid to delete

        Returns:
            bool: Whether or not this was successful
        """
        data = await self.read_factoid_data(guild, id)
        calls = await self.get_factoid_calls_by_factoid_id(guild, id)
        jobs = await self.get_factoid_jobs_by_factoid_id(guild, id)

        if not data:
            return False

        for call in calls:
            await call.delete()

        for job in jobs:
            # We need to clear the job from both the database and APScheduler
            await self.unschedule_job(job)
            await job.delete()

        await data.delete()
        return True

    async def move_factoid_call(
        self: Self,
        guild: discord.Guild,
        existing_name: str,
        new_factoid_data_id: int,
    ) -> bool:
        """
        Moves a FactoidCall to a different FactoidData entry.

        If the old FactoidData loses all calls, it is deleted.
        Returns True if the move succeeded.
        """
        call = await self.read_factoid_call(
            guild=guild,
            name=existing_name,
        )

        if call is None:
            return False

        old_factoid_data_id = call.factoid_data_id

        # Update the call to point to the new factoid
        await self.bot.models.FactoidCall.update.values(
            factoid_data_id=new_factoid_data_id
        ).where(
            (self.bot.models.FactoidCall.guild == str(guild.id))
            & (self.bot.models.FactoidCall.name == existing_name)
        ).gino.status()

        # Check if the old factoid is now orphaned
        remaining_calls = await self.get_factoid_calls_by_factoid_id(
            guild=guild,
            factoid_data_id=old_factoid_data_id,
        )

        # If there aren't any calls, prevent having orphaned factoids in the database at all
        if not remaining_calls:
            await self.delete_factoid_data_by_id(
                guild=guild,
                factoid_data_id=old_factoid_data_id,
            )

        return True

    async def get_all_factoids_for_guild(
        self: Self,
        guild: discord.Guild,
    ) -> list[FactoidView]:
        factoid_data = await self.bot.models.FactoidData.query.where(
            self.bot.models.FactoidData.guild == str(guild.id)
        ).gino.all()
        factoid_calls = await self.bot.models.FactoidCall.query.where(
            self.bot.models.FactoidCall.guild == str(guild.id)
        ).gino.all()

        calls_by_id: dict[int, list[str]] = {}

        for call in factoid_calls:
            calls_by_id.setdefault(
                call.factoid_data_id,
                [],
            ).append(call.name)

        views = []

        for factoid in factoid_data:
            views.append(
                FactoidView(
                    factoid_data_id=factoid.factoid_data_id,
                    message=factoid.message,
                    json_string=factoid.json_string,
                    flags=factoid.flags,
                    times_called=factoid.times_called,
                    create_time=factoid.create_time,
                    edit_time=factoid.edit_time,
                    calls=sorted(
                        calls_by_id.get(
                            factoid.factoid_data_id,
                            [],
                        )
                    ),
                )
            )

        return views

    async def increment_times_called_by_view(
        self: Self, guild: discord.Guild, factoid: FactoidView
    ) -> None:
        factoid.times_called += 1
        await self.update_factoid_data(
            guild=guild,
            factoid_data_id=factoid.factoid_data_id,
            times_called=factoid.times_called,
        )
        # Replace the factoid in the cache. No need to require a re-pull every call
        self.remove_from_cache(guild, factoid)
        self.add_to_cache(guild, factoid)

    async def handle_factoid_edit(
        self: Self, guild: discord.Guild, factoid: FactoidView
    ) -> None:
        """Sets the edit time of the factoid to now
        This also clears the factoid and factoid all cache after the edits

        Args:
            guild (discord.Guild): The guild this factoid is in
            factoid (FactoidView): The factoid to edit
        """
        await self.update_factoid_data(
            guild=guild,
            factoid_data_id=factoid.factoid_data_id,
            edit_time=datetime.datetime.utcnow(),
        )

        # Make sure the edited factoid is not in the cache
        self.remove_from_cache(guild, factoid)

        # Clear factoid all and factoid autocomplete caches
        self.clear_guild_caches(guild)

    # CACHE HELPERS

    def add_to_cache(self: Self, guild: discord.Guild, factoid: FactoidView) -> None:
        cache_key = self.generate_cache_key(guild, factoid.factoid_data_id)
        if cache_key not in self.factoid_cache:
            self.factoid_cache[cache_key] = factoid

    def remove_from_cache(
        self: Self, guild: discord.Guild, factoid: FactoidView
    ) -> None:
        cache_key = self.generate_cache_key(guild, factoid.factoid_data_id)
        if cache_key in self.factoid_cache:
            del self.factoid_cache[cache_key]

    def get_from_cache(
        self: Self, guild: discord.Guild, factoid_id: int
    ) -> FactoidView | None:
        cache_key = self.generate_cache_key(guild, factoid_id)
        if cache_key in self.factoid_cache:
            return self.factoid_cache[cache_key]
        return None

    def generate_cache_key(self: Self, guild: discord.Guild, factoid_id: int) -> str:
        return f"{guild.id}:{factoid_id}"

    def clear_guild_caches(self: Self, guild: discord.Guild) -> None:
        """This clears the guild wide caches, being factoid all and factoid autocomplete

        Args:
            guild (discord.Guild): The guild to clear the cache for
        """
        # This theoretically could be made better by being more targetted and efficient
        # There are a lot of cases where only some of this cache should be deleted
        # We delete it all anyway to avoid bugs

        # Clearing factoid all cache for this guild
        for entry in list(self.factoid_all_cache.keys()):
            if entry[0] == guild.id:
                del self.factoid_all_cache[entry]

        # clearing factoid autocomplete cache for this guild
        if guild.id in self.factoid_autocomplete_cache:
            del self.factoid_autocomplete_cache[guild.id]

    # OTHER HELPERS

    def can_channel_send_restricted(
        self: Self, channel: discord.abc.GuildChannel
    ) -> bool:
        """This checks if the given channel is in the restricted channel list.
        Can handle parsing threads

        Args:
            self (Self): _description_
            channel (discord.abc.GuildChannel): The channel trying to see the factoid

        Returns:
            bool: Whether the restricted factoid can be sent
        """
        if isinstance(channel, discord.Thread):
            channel = channel.parent

        restricted_channel_list = configuration.get_config_entry(
            channel.guild.id, "factoids_restricted_list"
        )

        if str(channel.id) in restricted_channel_list:
            return True
        return False

    def get_embed_from_factoid(
        self: Self, factoid: bot.models.FactoidData
    ) -> discord.Embed:
        """Gets the factoid embed from its database entry

        Args:
            factoid (bot.models.FactoidData): The factoid to get the json of

        Returns:
            discord.Embed: The embed of the factoid
        """
        if not factoid.json_string:
            return None

        embed_config = json.loads(factoid.json_string)

        return discord.Embed.from_dict(embed_config)

    async def confirm_factoid_deletion(
        self: Self,
        interaction: discord.Interaction,
        display_message: str,
        channel: discord.abc.GuildChannel,
        author: discord.Member,
    ) -> ui.ConfirmResponse:
        """Confirms if a factoid should be deleted/modified

        Args:
            factoid_name (str): The factoid that is being prompted for deletion
            channel (discord.abc.GuildChannel): The channel the factoid is being deleted in
            author (discord.Member): The member deleting the factoid
            fmt (str): Formatting for the returned message

        Returns:
            bool: Whether the factoid was deleted/modified
        """
        view = ui.Confirm()
        await view.send(
            message=display_message,
            channel=channel,
            author=author,
            interaction=interaction,
        )

        await view.wait()
        return view.value

    async def build_factoid_all(
        self: Self,
        guild: discord.Guild,
        factoids: list[FactoidView],
        use_file: bool,
    ) -> discord.File | str:
        """This builds the factoid all url or the yaml file

        Args:
            guild (discord.Guild): The guild to build factoid all for
            factoids (list[FactoidView]): The factoids to include in the all
            use_file (bool): Whether to force the use of a file or not

        Returns:
            discord.File | str: The final formatted factoid all
        """

        if use_file:
            return self.generate_factoid_all_file(guild, factoids)

        try:
            html = await self.generate_factoid_all_html(guild, factoids)

            if html is None:
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

            return url.replace(filename, f"selif/{filename}")

        except (gaierror, InvalidURL) as exception:
            log_channel = configuration.get_config_entry(
                guild.id,
                "core_logging_channel",
            )

            await self.bot.logger.send_log(
                message="Could not render/send all-factoid HTML",
                level=LogLevel.ERROR,
                context=LogContext(guild=guild),
                channel=log_channel,
                exception=exception,
            )

            return self.generate_factoid_all_file(guild, factoids)

    async def generate_factoid_all_html(
        self: Self,
        guild: discord.Guild,
        factoids: list[FactoidView],
    ) -> str:
        """Method to generate the html file contents

        Args:
            guild (discord.Guild): The guild the factoids are being pulled from
            factoids (list[FactoidView]): List of all factoids

        Returns:
            str: The result html file
        """

        # Should never hit this, but double check
        if not factoids:
            return None

        body_contents = ""

        for factoid in factoids:
            embed_text = " (embed)" if factoid.json_string else ""

            calls = sorted(factoid.calls)

            calls_text = f" [{', '.join(calls)}]"

            body_contents += (
                f"<li><code>{calls_text}{embed_text}"
                f" - {factoid.message}</code></li>"
            )

        body_contents = f"<ul>{body_contents}</ul>"

        return f"""
        <!DOCTYPE html>

        <html>
        <body>
        <h3>Factoids for {guild.name}</h3>
        {body_contents}
        <style>
        ul {{
            display: table;
            width: auto;
        }}

        ul li {{
        display: table-row;
        }}

        ul li:nth-child(even) {{
        background-color: lightgray;
        }} </style>

        </body>
        </html>
        """

    def generate_factoid_all_file(
        self: Self,
        guild: discord.Guild,
        factoids: list[FactoidView],
    ) -> discord.File:
        """Method to send the factoid list as a file instead of a paste

        Args:
            guild (discord.Guild): The guild the factoids are from
            factoids (list[FactoidView]): List of all factoids

        Returns:
            discord.File: The file, ready to upload to discord
        """
        # We should never be here, but just in case
        if not factoids:
            return None

        output_data = []

        for index, factoid in enumerate(factoids):

            calls = factoid.calls

            properties_str = (
                ", ".join(
                    prop.name.lower() for prop in Properties if factoid.flags & prop
                )
                or "None"
            )

            data = {
                "calls": calls,
                "message": factoid.message,
                "embed": bool(factoid.json_string),
                "properties": properties_str,
            }

            output_data.append(
                {
                    index: data,
                }
            )

        return discord.File(
            io.StringIO(yaml.dump(output_data)),
            filename=(
                f"factoids-for-server-{guild.id}-{datetime.datetime.utcnow()}.yaml"
            ),
        )

    async def generate_sendable_factoid(
        self: Self, guild: discord.Guild, factoid: FactoidView
    ) -> tuple[discord.Embed, str]:
        """This generates the embed and plaintext versions of a factoid, to prepare to be sent

        Args:
            guild (discord.Guild): The guild the factoid exists in
            factoid (FactoidView): The factoid to send

        Returns:
            tuple[discord.Embed, str]: The embed if created (or None), the plaintext version
        """
        plaintext = factoid.message
        if configuration.get_config_entry(guild.id, "factoids_disable_embeds"):
            return (None, plaintext)
        embed = None
        try:
            embed = self.get_embed_from_factoid(factoid)
        except TypeError as exception:
            asyncio.create_task(
                self.log_embed_fallback_exception(
                    factoid=factoid,
                    exception=exception,
                    guild=guild,
                )
            )

        return (embed, plaintext)

    async def log_factoid_send(
        self: Self,
        guild: discord.Guild,
        channel: discord.abc.GuildChannel,
        sender: discord.Member,
        factoid: FactoidView,
    ) -> None:
        """This sends a factoid call to the bot log channel

        Args:
            guild (discord.Guild): The guild the factoid was sent to
            channel (discord.abc.GuildChannel): The channel the factoid was sent to
            sender (discord.Member): The member who sent the factoid
            factoid (FactoidView): The factoid that was sent
        """

        log_channel = configuration.get_config_entry(guild.id, "core_logging_channel")
        await self.bot.logger.send_log(
            message=(
                f"Sending factoid: `[{', '.join(factoid.calls)}]` (triggered by {sender} in"
                f" #{channel.name})"
            ),
            level=LogLevel.INFO,
            context=LogContext(guild=guild, channel=channel),
            channel=log_channel,
        )

    def send_factoid_to_irc(
        self: Self,
        channel: discord.abc.Messageable,
        factoid: FactoidView,
        author: discord.Member,
    ) -> None:
        """If relevant, will send a factoid to the bridged IRC channel

        Args:
            channel (discord.abc.Messageable): The discord channel the message was sent in
            factoid (FactoidView): The factoid that was sent
            author (discord.Member): The member who sent the factoid. May be the bot
        """
        irc_config = self.bot.file_config.api.irc
        if not irc_config.enable_irc:
            return

        self.bot.irc.irc_cog.handle_factoid(
            channel=channel,
            factoid=factoid,
            author=author,
        )

    async def send_factoid_to_logger(
        self: Self,
        factoid_message_object: discord.Message,
        factoid_caller: discord.Member,
        channel: discord.abc.GuildChannel | discord.Thread,
        factoid_message: str,
    ) -> None:
        """Send a factoid call to the logger function

        Args:
            factoid_message_object (discord.Message): The message that the factoid is sent in
            factoid_caller (discord.Member): The person who called the factoid
            channel (discord.abc.GuildChannel | discord.Thread): The channel the
                factoid was sent in
            factoid_message (str): The plaintext message content of the factoid
        """
        # Don't allow logging if extension is disabled
        if "moderation.logger" not in configuration.get_config_entry(
            factoid_caller.guild.id, "core_enabled_extensions"
        ):
            return

        target_logging_channel = await function_logger.pre_log_checks(self.bot, channel)
        if not target_logging_channel:
            return

        await function_logger.send_message(
            self.bot,
            factoid_message_object,
            factoid_caller,
            channel,
            target_logging_channel,
            content_override=factoid_message,
            special_flags=["Factoid call"],
        )

    def check_valid_name(self: Self, name: str) -> bool:
        """This checks if the name of a factoid is valid or not

        Args:
            name (str): The name of the factoid to check

        Returns:
            bool: Whether this name is allowable
        """
        # Rule 1: name must exist
        if not name:
            return False
        # Rule 2: No commas
        elif "," in name:
            return False

        # Factoid name passed all the rules
        return True

    def check_valid_message(self: Self, message: str) -> bool:
        """This checks if the message of a factoid is valid or not

        Args:
            message (str): The message of the factoid to check

        Returns:
            bool: Whether this message is allowable
        """
        mention_regex = re.compile(r"(@everyone|@here|<@[!&]?\d+>|<#\d+>)")
        # Rule 1, no mentions
        if mention_regex.search(message):
            return False
        # Rule 2, ensure length is no longer than discord can handle
        elif len(message) > 2000:
            return False

        # Message passes all rules
        return True

    def create_json_file(self: Self, factoid: FactoidView) -> discord.File:
        """This takes a factoid and pulls the json string, and turns it into a file
        Designed to be used to send a json file in a discord message

        Args:
            factoid (FactoidView): The factoid to make the json file of

        Returns:
            discord.File: The json file representing the embed of this factoid
        """
        formatted = json.dumps(json.loads(factoid.json_string), indent=4)
        json_file = discord.File(
            io.StringIO(formatted),
            filename=(
                f"factoid-{factoid.factoid_data_id}-embed-config-{datetime.datetime.utcnow()}.json"
            ),
        )
        return json_file

    async def log_embed_fallback_exception(
        self: Self,
        factoid: FactoidView,
        exception: Exception,
        guild: discord.Guild,
        channel: discord.abc.GuildChannel = None,
    ) -> None:
        """This logs an error log if a factoid embed failed, causing a fallback to be sent

        Args:
            factoid (FactoidView): The factoid that had the problem
            exception (Exception): The exception generated when making or sending the embed
            guild (discord.Guild): The guild this happened in
            channel (discord.abc.GuildChannel, optional): The channel the factoid was going to be sent in. Defaults to None.
        """
        log_channel = configuration.get_config_entry(guild.id, "core_logging_channel")
        await self.bot.logger.send_log(
            message=(
                f"Unable to send embed for factoid `[{', '.join(factoid.calls)}]`, "
                "sending fallback."
            ),
            level=LogLevel.ERROR,
            context=LogContext(guild=guild, channel=channel),
            channel=log_channel,
            exception=exception,
        )

    async def generate_json_string_from_file(
        self: Self, interaction: discord.Interaction, uploaded_file: discord.Attachment
    ) -> str:

        if not uploaded_file.filename.endswith(".json"):
            await self.respond_error_embed(
                interaction, "I don't recognize your upload as a JSON file."
            )
            return

        try:
            json_bytes = await uploaded_file.read()
            attachment_json = json.loads(json_bytes.decode("UTF-8"))
            embed_json_string = json.dumps(attachment_json)

        except Exception:
            await self.respond_error_embed(
                interaction, message="I couldn't parse the uploaded JSON file."
            )
            return

        return embed_json_string

    def compute_embed_hash(self: Self, embed: discord.Embed) -> str:
        """This generates a hash from a discords embed content, for comparison purposes
        This allows us to normalize the embed we are about to send and the embed we previously sent

        Args:
            embed (discord.Embed): The embed we want to normalize

        Returns:
            str: The hash of the embed to compare
        """

        # I hate everything about this
        # This is all because of discord CDN links

        # Do some parsing to attempt to ensure embeds are the same
        def normalize_discord_url(url: str | None) -> str | None:
            if not url:
                return None

            parsed_url = urlsplit(url)
            return urlunsplit(
                (parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "")
            )

        def normalize_inline(value):
            if value is None:
                return False
            return bool(value)

        embed_data = {
            "author": (
                {
                    "name": embed.author.name if embed.author else None,
                    "icon_url": normalize_discord_url(embed.author.icon_url),
                    "url": normalize_discord_url(embed.author.url),
                }
                if embed.author
                else None
            ),
            "footer": (
                {
                    "text": embed.footer.text if embed.footer else None,
                    "icon_url": normalize_discord_url(embed.footer.icon_url),
                }
                if embed.footer
                else None
            ),
            "color": embed.color.value if embed.color else None,
            "fields": [
                {
                    "name": field.name,
                    "value": field.value,
                    "inline": normalize_inline(field.inline),
                }
                for field in embed.fields
            ],
            "image": normalize_discord_url(embed.image.url),
            "thumbnail": normalize_discord_url(embed.thumbnail.url),
            "title": embed.title,
            "description": embed.description,
            "url": normalize_discord_url(embed.url),
            "timestamp": embed.timestamp.isoformat() if embed.timestamp else None,
        }

        normalized_json = json.dumps(embed_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(normalized_json.encode("utf-8")).hexdigest()

    # INTERACTION RESPONSE BOILERPLATE

    async def check_protected(
        self: Self, interaction: discord.Interaction, factoid: FactoidView
    ) -> bool:
        """This takes a factoid and ensures its not protected
        If the factoid is protected, this will respond to the interaction

        Args:
            interaction (discord.Interaction): The interaction calling the command
            factoid (FactoidView): The factoid attempting to be edited

        Returns:
            bool: True if protected, False if unprotected
        """
        if factoid.flags & Properties.PROTECTED:
            await self.respond_error_embed(
                interaction,
                f"The factoid `[{', '.join(factoid.calls)}]` is protected and cannot be edited.",
            )
            return True
        return False

    async def respond_error_embed(
        self: Self, interaction: discord.Interaction, message: str
    ) -> None:
        """This formats a denial embed and responds to the interaction with it.
        Will always respond ephemerally, will handle followup if needed

        Args:
            interaction (discord.Interaction): The interaction to respond to
            message (str): The message to include
        """
        embed = auxiliary.prepare_deny_embed(message=message)

        if interaction.response.is_done():
            await interaction.followup.send(
                embed=embed,
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    async def get_valid_factoid(
        self: Self, interaction: discord.Interaction, factoid_name: str
    ) -> FactoidView | None:
        """This gets a factoid by factoid name
        If the factoid does not exist, the interaction is responded to

        Args:
            interaction (discord.Interaction): The interaction that called for lookup
            factoid_name (str): The factoid name to lookup

        Returns:
            FactoidView | None: The factoid, if it exists. None if no factoid exists
        """
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )

        # We can't alias a factoid if it doesn't exist
        if not factoid:
            await self.respond_error_embed(
                interaction, f"The factoid `{factoid_name}` doesn't exist!"
            )

        return factoid

    # AUTOFILL
    async def setup_autocomplete_cache(self: Self, guild: discord.Guild) -> None:
        """This calls the database and creates a cache for the passed guild for the autocomplete
        This cache contains a mapping of names to flags

        Args:
            guild (discord.Guild): The guild to build the cache for
        """
        factoids = (
            await self.bot.db.select(
                [
                    self.bot.models.FactoidCall.name,
                    self.bot.models.FactoidData.flags,
                ]
            )
            .select_from(
                self.bot.models.FactoidCall.join(
                    self.bot.models.FactoidData,
                    self.bot.models.FactoidCall.factoid_data_id
                    == self.bot.models.FactoidData.factoid_data_id,
                )
            )
            .where(self.bot.models.FactoidCall.guild == str(guild.id))
            .gino.all()
        )

        cache = [
            (
                factoid.name.lower(),
                factoid.flags,
            )
            for factoid in factoids
        ]

        cache.sort(key=lambda x: x[0])

        self.factoid_autocomplete_cache[guild.id] = cache

    async def generate_factoid_autocomplete_list(
        self: Self,
        interaction: discord.Interaction,
        current: str,
        hidden_flags: Properties = Properties(0),
    ) -> list[app_commands.Choice[str]]:
        """This autocomplete list is capable of returning all factoids, filtering by no properties
        It is setup in a way where it can be called with a list of flags to hide
        This is not designed to be used as a direct call

        Args:
            interaction (discord.Interaction): The interaction calling for autocomplete
            current (str): The current text in the factoid name field
            hidden_flags (Properties, optional): The properties to exclude from the list.
                Defaults to Properties(0).

        Returns:
            list[app_commands.Choice[str]]: The list of choices matching the user input and flag filter
        """
        guild = interaction.guild
        if guild is None:
            return []

        if guild.id not in self.factoid_autocomplete_cache:
            await self.setup_autocomplete_cache(guild)

        current = current.lower()
        cached = self.factoid_autocomplete_cache.get(guild.id, [])

        matches: list[app_commands.Choice[str]] = []

        for name, flags in cached:
            if not name.startswith(current):
                continue

            if flags & hidden_flags:
                continue

            matches.append(
                app_commands.Choice(
                    name=name,
                    value=name,
                )
            )

            if len(matches) >= 10:
                break

        return matches

    async def property_factoid_autocomplete(
        self: Self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """This function is designed to return ALL factoids, regardless of property flags
        Designed for use exclusively in the /factoid property command

        Args:
            interaction (discord.Interaction): The interaction calling for autocomplete
            current (str): The current text in the factoid name field

        Returns:
            list[app_commands.Choice[str]]: The list of choices matching to show to the user
        """
        return await self.generate_factoid_autocomplete_list(
            interaction,
            current,
        )

    async def editing_factoid_autocomplete(
        self: Self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """This autocomplete list will hide hidden and protected factoids from the autocomplete list
        This is designed for use when editing factoids

        Args:
            interaction (discord.Interaction): The interaction calling for autocomplete
            current (str): The current text in the factoid name field

        Returns:
            list[app_commands.Choice[str]]: The list of choices matching to show to the user
        """
        return await self.generate_factoid_autocomplete_list(
            interaction,
            current,
            hidden_flags=(Properties.HIDDEN | Properties.PROTECTED),
        )

    async def filtered_factoid_autocomplete(
        self: Self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """This hides hidden and disabled facotids, and restricted factoids if they cannot be used in the current channel
        This is designed for user forward commands, like /factoid call and /factoid info

        Args:
            interaction (discord.Interaction): The interaction calling for autocomplete
            current (str): The current text in the factoid name field

        Returns:
            list[app_commands.Choice[str]]: The list of choices matching to show to the user
        """
        hidden_flags = Properties.HIDDEN | Properties.DISABLED

        if not self.can_channel_send_restricted(interaction.channel):
            hidden_flags |= Properties.RESTRICTED

        return await self.generate_factoid_autocomplete_list(
            interaction,
            current,
            hidden_flags=hidden_flags,
        )

    # COMMANDS

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="alias",
        description="Creates an alias for an existing factoid call",
    )
    @app_commands.autocomplete(existing_factoid=editing_factoid_autocomplete)
    async def factoid_alias_command(
        self: Self,
        interaction: discord.Interaction,
        existing_factoid: str,
        new_factoid: str,
    ) -> None:
        existing_factoid = existing_factoid.lower()
        new_factoid = new_factoid.lower()
        if not self.check_valid_name(new_factoid):
            await self.respond_error_embed(
                interaction,
                f"The factoid name `{new_factoid}` is invalid and cannot be used!",
            )
            return

        if new_factoid == existing_factoid:
            await self.respond_error_embed(
                interaction, f"You cannot alias a factoid to itself!"
            )
            return

        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=existing_factoid
        )
        if not factoid:
            return

        # No aliases on protected factoids
        if await self.check_protected(interaction, factoid):
            return

        new_factoid_db = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=new_factoid
        )

        # If the existing and new calls already point to the same factoid, there is nothing to do
        if new_factoid_db and factoid.factoid_data_id == new_factoid_db.factoid_data_id:
            await self.respond_error_embed(
                interaction,
                f"The factoid `{new_factoid}` is already an alias of `{existing_factoid}`.",
            )
            return

        # If the new_factoid already exists but point elsewhere, we need to ask the user for confirmation
        if new_factoid_db:

            # No aliases on protected factoids
            if await self.check_protected(interaction, new_factoid_db):
                return

            await interaction.response.defer()
            confirmation_response = await self.confirm_factoid_deletion(
                interaction=interaction,
                display_message=f"The factoid `{new_factoid}` already exists. Should I overwrite it?",
                channel=interaction.channel,
                author=interaction.user,
            )
            if confirmation_response == ui.ConfirmResponse.TIMEOUT:
                return
            elif confirmation_response == ui.ConfirmResponse.DENIED:
                await self.respond_error_embed(
                    interaction,
                    message=f"The factoid `{new_factoid}` was not replaced.",
                )
                return
            else:
                await self.move_factoid_call(
                    guild=interaction.guild,
                    existing_name=new_factoid,
                    new_factoid_data_id=factoid.factoid_data_id,
                )
        else:
            await self.create_factoid_call(
                guild=interaction.guild,
                name=new_factoid,
                factoid_data_id=factoid.factoid_data_id,
            )
        embed = auxiliary.prepare_confirm_embed(
            message=f"Successfully added the alias `{new_factoid}` for `{existing_factoid}`",
        )

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.handle_factoid_edit(interaction.guild, factoid)
        if new_factoid_db:
            await self.handle_factoid_edit(interaction.guild, new_factoid_db)

        # Depending on the path took to get here, we may need to followup
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed)
        else:
            await interaction.response.send_message(embed=embed)

    @factoid_app_group.command(
        name="all",
        description="Sends a configurable list of all factoids.",
        extras={"ephemeral_error": True},
    )
    async def factoid_all_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_property: Properties = "",
        force_file: bool = False,
        show_all: bool = False,
    ) -> None:
        all_factoids = await self.get_all_factoids_for_guild(guild=interaction.guild)

        if not all_factoids:
            await self.respond_error_embed(
                interaction, "No factoids have been created for this guild"
            )
            return

        # Property filters only avaiable to manage roles
        if factoid_property or show_all:
            await has_given_factoids_role(
                interaction.guild,
                interaction.user,
                configuration.get_config_entry(
                    interaction.guild.id, "factoids_manage_roles"
                ),
            )

        # Determine whether restricted factoids should be visible here
        should_show_restricted = self.can_channel_send_restricted(
            interaction.channel,
        )

        # Top priority is abiding by show_all
        # If not but a specific property is requested, show that
        # Otherwise, show a normal filtered list, no hidden, no disabled, no restricted
        if show_all:
            filtered_factoids = all_factoids
        elif factoid_property:
            filtered_factoids = [
                factoid for factoid in all_factoids if factoid.flags & factoid_property
            ]
        else:
            filtered_factoids = [
                factoid
                for factoid in all_factoids
                if (
                    # Never show hidden factoids normally
                    not (factoid.flags & Properties.HIDDEN)
                    # Never show disabled factoids normally
                    and not (factoid.flags & Properties.DISABLED)
                    # Restricted factoids depend on channel
                    and (
                        should_show_restricted
                        or not (factoid.flags & Properties.RESTRICTED)
                    )
                )
            ]

        # Bulding a cache key to cache factoid all links
        if show_all:
            cache_mode = "all"
            property_value = 0
        elif factoid_property:
            cache_mode = "property"
            property_value = factoid_property
        elif should_show_restricted:
            cache_mode = "default_with_restricted"
            property_value = 0
        else:
            cache_mode = "default"
            property_value = 0

        cache_key = (
            interaction.guild.id,
            cache_mode,
            property_value,
        )

        filtered_factoids.sort(key=lambda factoid: factoid.calls[0])
        if not filtered_factoids:
            await self.respond_error_embed(
                interaction, "No factoids could be found matching your filter"
            )
            return

        # If the linx server isn't configured, we must make it a file
        if not self.bot.file_config.api.api_url.linx:
            force_file = True

        await interaction.response.defer(ephemeral=True)

        cached_factoid_all = self.factoid_all_cache.get(cache_key)

        if cached_factoid_all and not force_file:
            factoid_all = cached_factoid_all
        else:
            factoid_all = await self.build_factoid_all(
                guild=interaction.guild, factoids=filtered_factoids, use_file=force_file
            )

        if not factoid_all:
            await self.respond_error_embed(
                interaction, "Something went wrong generating the list of factoids"
            )
            return

        # If we got a file, send it.
        if isinstance(factoid_all, discord.File):
            await interaction.followup.send(file=factoid_all, ephemeral=True)
            return

        # If we didn't pull factoid all from the cache, add it to the cache
        if not cached_factoid_all:
            self.factoid_all_cache[cache_key] = factoid_all

        embed = auxiliary.prepare_confirm_embed(factoid_all)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @factoid_app_group.command(
        name="call",
        description="Calls a factoid from the database and sends it publicy in the channel.",
        extras={"ephemeral_error": True},
    )
    @app_commands.autocomplete(factoid_name=filtered_factoid_autocomplete)
    async def factoid_call_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
        member_to_ping: discord.Member = None,
    ) -> None:
        """This is an app command version of typing {prefix}call
        This is the preferred method of getting factoids

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid name to search for and print
            member_to_ping (discord.Member): A member to ping in the output
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        # Check if factoid is disabled. If so, don't send it
        if factoid.flags & Properties.DISABLED:
            await self.respond_error_embed(
                interaction, f"The factoid `{factoid_name}` is disabled."
            )
            return

        # Check if factoid is restricted. If so, check if we can call it
        if (
            factoid.flags & Properties.RESTRICTED
            and not self.can_channel_send_restricted(interaction.channel)
        ):
            await self.respond_error_embed(
                interaction,
                f"The factoid `{factoid_name}` is restricted and not allowed in this channel.",
            )
            return

        embed, plaintext_content = await self.generate_sendable_factoid(
            interaction.guild, factoid
        )

        # Log in the background
        asyncio.create_task(
            self.log_factoid_send(
                guild=interaction.guild,
                channel=interaction.channel,
                sender=interaction.user,
                factoid=factoid,
            )
        )

        content = ""
        if member_to_ping:
            content = member_to_ping.mention

        embed_sent = False
        view = ButtonView(interaction.user.id, factoid)
        if embed:
            try:
                # Attempt to send the message with the embed in it
                await interaction.response.send_message(
                    content=content,
                    embed=embed,
                    view=view,
                )
                view.message = await interaction.original_response()
                embed_sent = True
            # If something breaks, also log it
            except discord.errors.HTTPException as exception:
                asyncio.create_task(
                    self.log_embed_fallback_exception(
                        factoid=factoid,
                        exception=exception,
                        guild=interaction.guild,
                        channel=interaction.channel,
                    )
                )

        # Either no embed exists, or the embed failed to send for some reason.
        # We will send the plaintext content of the factoid in this case
        if not embed_sent:
            content += f" {plaintext_content}"
            content = content.strip()
            if len(content) > 2000:
                await self.respond_error_embed(
                    interaction,
                    f"The factoid `{factoid_name}` is too long and cannot be sent on discord.",
                )
                return

            # The can't see button is not needed in plaintext cases
            view.remove_item(view.cant_see_button)
            await interaction.response.send_message(content=content, view=view)
            view.message = await interaction.original_response()

        # IRC connection
        self.send_factoid_to_irc(interaction.channel, factoid, interaction.user)

        # Logger connection
        sent_message = await interaction.original_response()
        await self.send_factoid_to_logger(
            sent_message, interaction.user, interaction.channel, factoid.message
        )

        # Increase times called
        await self.increment_times_called_by_view(
            guild=interaction.guild, factoid=factoid
        )

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="create",
        description="Creates a new factoid by name",
        extras={"ephemeral_error": True},
    )
    async def factoid_create_command(
        self: Self, interaction: discord.Interaction, factoid_name: str
    ) -> None:
        factoid_name = factoid_name.lower()
        # Only ever attempt to add a factoid if it doesn't exist
        existing_factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )
        if existing_factoid:
            await self.respond_error_embed(
                interaction, f"The factoid `{factoid_name}` already exists"
            )
            return

        if not self.check_valid_name(factoid_name):
            await self.respond_error_embed(
                interaction,
                f"The factoid name `{factoid_name}` is invalid and cannot be used!",
            )
            return

        form = FactoidModal(factoid_name, edit_mode=False)
        await interaction.response.send_modal(form)
        await form.wait()

        if not self.check_valid_message(form.plaintext.component.value):
            await self.respond_error_embed(
                interaction, "The message content is invalid and cannot be used!"
            )
            return

        embed_json_string = ""
        if form.embed.component.values:
            embed_json_string = self.generate_json_string_from_file(
                interaction, form.embed.component.values[0]
            )
            if not embed_json_string:
                return

        selected = set(form.properties.component.values)

        property_binary = sum(int(value) for value in selected)

        factoid = await self.bot.models.FactoidData.create(
            guild=str(interaction.guild.id),
            message=form.plaintext.component.value,
            json_string=embed_json_string,
            flags=property_binary,
        )
        try:
            await self.create_factoid_call(
                guild=interaction.guild,
                name=factoid_name,
                factoid_data_id=factoid.factoid_data_id,
            )
        except Exception as exc:
            await factoid.delete()
            raise exc

        # We must update the factoid all and autocomplete list
        self.clear_guild_caches(interaction.guild)

        embed = auxiliary.prepare_confirm_embed(
            message=f"Your factoid `{factoid_name}` was successfully created!",
        )
        await interaction.followup.send(embed=embed)

        # Send the factoid, and embed json if exists, to the user
        await interaction.followup.send(content=factoid.message, ephemeral=True)
        if embed_json_string:
            try:
                embed = self.get_embed_from_factoid(factoid=factoid)
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as exc:
                await self.respond_error_embed(
                    interaction, f"The embed you uploaded failed: {exc}"
                )

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="dealias",
        description="Deletes an alias for an existing factoid call",
    )
    @app_commands.autocomplete(factoid_name=editing_factoid_autocomplete)
    async def factoid_dealias_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
    ) -> None:
        """This deletes an alias from an existing factoid
        This will not delete the FactoidData entry

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid to dealias
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        # No edits on protected factoids
        if await self.check_protected(interaction, factoid):
            return

        # Only allowed to dealias if this wouldn't require deleting the entire factoid
        if len(factoid.calls) == 1:
            await self.respond_error_embed(
                interaction, f"The factoid `{factoid_name}` has no other aliases."
            )
            return

        await self.bot.models.FactoidCall.delete.where(
            (self.bot.models.FactoidCall.guild == str(interaction.guild.id))
            & (self.bot.models.FactoidCall.name == factoid_name)
        ).gino.status()
        factoid.calls.remove(factoid_name)
        remaining_aliases = ", ".join(factoid.calls)
        embed = auxiliary.prepare_confirm_embed(
            message=f"The factoid alias `{factoid_name}` was removed. Remaining aliases: `{remaining_aliases}`"
        )

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.handle_factoid_edit(interaction.guild, factoid)

        await interaction.response.send_message(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="delete",
        description="Deletes a factoid, all aliases and all jobs",
    )
    @app_commands.autocomplete(factoid_name=editing_factoid_autocomplete)
    async def factoid_delete_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
    ) -> None:
        """This deletes a factoid from the database entirely
        All FactoidCall and FactoidJob entries will be deleted

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid to dealias
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        # No edits on protected factoids
        if await self.check_protected(interaction, factoid):
            return

        await interaction.response.defer()
        confirmation_response = await self.confirm_factoid_deletion(
            interaction=interaction,
            display_message=f"Are you sure you want to delete the factoid `[{', '.join(factoid.calls)}]`?",
            channel=interaction.channel,
            author=interaction.user,
        )
        if confirmation_response == ui.ConfirmResponse.TIMEOUT:
            return
        elif confirmation_response == ui.ConfirmResponse.DENIED:
            await self.respond_error_embed(
                interaction, f"The factoid `{factoid_name}` was not deleted."
            )
            return

        await self.delete_factoid_data_by_id(interaction.guild, factoid.factoid_data_id)

        # We must update the factoid all and autocomplete list
        self.clear_guild_caches(interaction.guild)

        # Remove factoid from cache after deleting
        self.remove_from_cache(interaction.guild, factoid)

        embed = auxiliary.prepare_confirm_embed(
            f"The factoid `[{', '.join(factoid.calls)}]` was deleted"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="edit",
        description="Edits an existing factoids message or embed",
    )
    @app_commands.autocomplete(factoid_name=editing_factoid_autocomplete)
    async def factoid_edit_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
    ) -> None:
        """This edits an existing factoid, allowing changes to the properties, message, and embed

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid to edit
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        # No edits on protected factoids
        if await self.check_protected(interaction, factoid):
            return

        form = FactoidModal(factoid_name, edit_mode=True, factoid=factoid)
        await interaction.response.send_modal(form)
        await form.wait()

        if not self.check_valid_message(form.plaintext.component.value):
            await self.respond_error_embed(
                interaction, "The message content is invalid and cannot be used!"
            )
            return

        show_plaintext = False
        show_embed = False

        if form.plaintext.component.value != factoid.message:
            show_plaintext = True

        # Embed handling.
        embed_json_string = ""
        embed_choice = form.json_action.component.value
        if embed_choice == "keep":
            embed_json_string = factoid.json_string
        elif embed_choice == "replace":
            show_embed = True
            # In order to replace we must have a json file
            if not form.embed.component.values:
                await self.respond_error_embed(
                    interaction,
                    "The json file was requested to be replaced, but no file was uploaded. No edits were made.",
                )
                return

            embed_json_string = self.generate_json_string_from_file(
                interaction, form.embed.component.values[0]
            )
            if not embed_json_string:
                return

        # If the factoid was not edited, do nothing
        if not show_embed and not show_plaintext:
            await self.respond_error_embed(
                interaction,
                "It doesn't appear any edits were made to this factoid. No edits were made.",
            )
            return

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.handle_factoid_edit(interaction.guild, factoid)

        factoid = await self.update_factoid_data(
            guild=interaction.guild,
            factoid_data_id=factoid.factoid_data_id,
            message=form.plaintext.component.value,
            json_string=embed_json_string,
        )

        embed = auxiliary.prepare_confirm_embed(
            message=f"Your factoid `{factoid_name}` was successfully edited!",
        )
        await interaction.followup.send(embed=embed)

        # If plaintext or embed was edited, show the new version to the user
        if show_plaintext:
            await interaction.followup.send(content=factoid.message, ephemeral=True)
        if show_embed:
            try:
                embed = self.get_embed_from_factoid(factoid=factoid)
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as exc:
                await self.respond_error_embed(
                    interaction, f"The embed you uploaded failed: {exc}"
                )

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.check(has_admin_factoids_role)
    @factoid_app_group.command(
        name="flush",
        description="Flushes cached factoids for the current guild",
    )
    async def factoid_flush_command(
        self: Self,
        interaction: discord.Interaction,
    ) -> None:
        """Command designed for fixing issues and debugging.
        Will empty the cache for the current guild

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
        """
        guild_id = interaction.guild.id

        factoid_cache_removed = 0
        factoid_all_cache_removed = 0
        autocomplete_cache_removed = 0

        # Clear factoid cache
        for entry in list(self.factoid_cache.keys()):
            if entry.startswith(str(guild_id)):
                del self.factoid_cache[entry]
                factoid_cache_removed += 1

        # Clear factoid all cache
        for entry in list(self.factoid_all_cache.keys()):
            if entry[0] == guild_id:
                del self.factoid_all_cache[entry]
                factoid_all_cache_removed += 1

        # Clear autocomplete cache
        if guild_id in self.factoid_autocomplete_cache:
            autocomplete_cache_removed = 1
            del self.factoid_autocomplete_cache[guild_id]

        embed = auxiliary.prepare_confirm_embed(
            "\n".join(
                [
                    f"FactoidView cache cleared: {factoid_cache_removed}",
                    f"FactoidAll cache cleared: {factoid_all_cache_removed}",
                    f"Autocomplete cache cleared: {autocomplete_cache_removed}",
                ]
            )
        )

        await interaction.response.send_message(embed=embed)

    @factoid_app_group.command(
        name="info",
        description="Gets information about a factoid and displays it to the user.",
        extras={"ephemeral_error": True},
    )
    @app_commands.autocomplete(factoid_name=filtered_factoid_autocomplete)
    async def factoid_info_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
    ) -> None:
        """This gets information about a given factoid from the database and displays it to the user

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid name to display information for
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        has_embed = bool(factoid.json_string)

        embed = discord.Embed(
            title=f"Info about `{factoid_name}`", description=factoid.message
        )
        embed.color = discord.Color.blue()
        embed.add_field(name="Calls", value=f"`[{', '.join(factoid.calls)}]`")
        embed.add_field(name="Time called", value=factoid.times_called)
        embed.add_field(name="Embed", value=has_embed)

        # Handle properties different to convert from into to string
        properties_str = (
            ", ".join(prop.name.lower() for prop in Properties if factoid.flags & prop)
            or "None"
        )
        embed.add_field(name="Properties", value=properties_str)

        embed.add_field(
            name="Date of creation", value=f"<t:{int(factoid.create_time.timestamp())}>"
        )
        embed.add_field(
            name="Last edit", value=f"<t:{int(factoid.edit_time.timestamp())}>"
        )

        jobs = await self.get_factoid_jobs_by_factoid_id(
            interaction.guild, factoid.factoid_data_id
        )
        if jobs:
            job_lines = []

            for job in jobs:
                channel = interaction.guild.get_channel(int(job.channel))

                if channel:
                    job_lines.append(f"{channel.mention} - `{job.cron}`")
                else:
                    job_lines.append(f"Unknown channel ({job.channel}) - `{job.cron}`")

            embed.add_field(
                name=f"Jobs ({len(jobs)})",
                value="\n".join(job_lines),
            )

        if has_embed:
            view = InfoEmbedButtons(interaction.user.id, factoid, self)
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
            view.message = interaction.original_response()
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @factoid_app_group.command(
        name="json",
        description="Gets the json file for the embed of this factoid",
    )
    @app_commands.autocomplete(factoid_name=editing_factoid_autocomplete)
    async def factoid_json_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
    ) -> None:
        """This gets information about a given factoid from the database and displays it to the user

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid name to display information for
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        if not factoid.json_string:
            await self.respond_error_embed(
                interaction,
                f"The factoid `{factoid_name}` doesn't have any embed configured!",
            )
            return

        json_file = self.create_json_file(factoid)

        await interaction.response.send_message(file=json_file)

    @factoid_loop_commands.command(
        name="all",
        description="Displays all active factoid loops for this guild",
    )
    async def factoid_loop_all_command(
        self: Self,
        interaction: discord.Interaction,
    ) -> None:
        """If any jobs exist, this will get and display all factoid jobs to the use

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
        """
        jobs = await self.get_all_jobs_for_guild(interaction.guild)
        if not jobs:
            await self.respond_error_embed(
                interaction, "There are no configured jobs for this guild"
            )
            return

        embed = discord.Embed(title=f"Factoid loop for {interaction.guild.name}")
        embed.color = discord.Color.blue()
        job_lines = []

        for job in jobs:
            factoid = await self.get_factoid_view_by_id(
                interaction.guild, job.factoid_data_id
            )
            channel = interaction.guild.get_channel(int(job.channel))

            if channel:
                job_lines.append(
                    f"`[{', '.join(factoid.calls)}]` - {channel.mention} - `{job.cron}`"
                )
            else:
                job_lines.append(
                    f"`[{', '.join(factoid.calls)}]` - Unknown channel ({job.channel}) - `{job.cron}`"
                )

        embed.description = "\n".join(job_lines)
        await interaction.response.send_message(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_loop_commands.command(
        name="create",
        description="Creates a new factoid loop job in the specified channel",
    )
    @app_commands.autocomplete(factoid_name=editing_factoid_autocomplete)
    async def factoid_loop_create_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
        channel: discord.abc.GuildChannel,
        cron: str,
    ) -> None:
        """This edits an existing factoid, allowing changes to the properties, message, and embed

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid to edit
            channel (discord.abc.GuildChannel): The channel to put this loop in
            cron (str): The crontab syntax to use for this job
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        if await self.check_protected(interaction, factoid):
            return

        # We can only have 1 factoid have a job per channel
        existing_job = await self.bot.models.FactoidJob.query.where(
            (self.bot.models.FactoidJob.guild == str(interaction.guild.id))
            & (self.bot.models.FactoidJob.factoid_data_id == factoid.factoid_data_id)
            & (self.bot.models.FactoidJob.channel == str(channel.id))
        ).gino.all()
        if existing_job:
            await self.respond_error_embed(
                interaction,
                f"The factoid `{factoid_name}` already has a job in {channel.mention}.",
            )
            return

        await interaction.response.defer()

        # Use APSchduler to determine if the cron syntax is valid before scheduling
        trigger = CronTrigger.from_crontab(cron)
        now = datetime.datetime.utcnow()
        run_at = trigger.get_next_fire_time(None, now)

        if run_at is None:
            await self.respond_error_embed(f"The cron expression: `{cron}` is invalid.")

        job_data = await self.bot.models.FactoidJob.create(
            guild=str(interaction.guild.id),
            factoid_data_id=factoid.factoid_data_id,
            channel=str(channel.id),
            cron=cron,
        )
        await self.register_job(job_data)

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.handle_factoid_edit(interaction.guild, factoid)

        embed = auxiliary.prepare_confirm_embed(
            f"The loop in {channel.mention} for factoid `{factoid_name}` was created successfully"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_loop_commands.command(
        name="delete",
        description="Deletes an existing factoid loop job based on name and channel",
    )
    @app_commands.autocomplete(factoid_name=editing_factoid_autocomplete)
    async def factoid_loop_delete_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
        channel: discord.abc.GuildChannel,
    ) -> None:
        """This edits an existing factoid, allowing changes to the properties, message, and embed

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid to edit
            channel (discord.abc.GuildChannel): The channel to put this loop in
            cron (str): The crontab syntax to use for this job
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        # No edits on protected factoids
        if await self.check_protected(interaction, factoid):
            return

        factoid_job = await self.read_factoid_job_by_channel(
            guild=interaction.guild,
            factoid_data_id=factoid.factoid_data_id,
            channel=channel,
        )

        if not factoid_job:
            await self.respond_error_embed(
                interaction,
                f"The factoid `{factoid_name}` doesn't have a job in {channel.mention}!",
            )
            return

        await interaction.response.defer()
        # We need to cancel the job in APScheduler and delete the database entry
        await self.unschedule_job(factoid_job)
        await factoid_job.delete()

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.handle_factoid_edit(interaction.guild, factoid)

        embed = auxiliary.prepare_confirm_embed(
            f"The loop in {channel.mention} for factoid `{factoid_name}` was deleted successfully"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_loop_commands.command(
        name="edit",
        description="Edits an existing factoid loop job based on name and channel",
    )
    @app_commands.autocomplete(factoid_name=editing_factoid_autocomplete)
    async def factoid_loop_edit_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
        channel: discord.abc.GuildChannel,
        cron: str,
    ) -> None:
        """This edits an existing job, changing the cron syntax

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
            factoid_name (str): The factoid to edit
            channel (discord.abc.GuildChannel): The channel the job to edit is in
            cron (str): The crontab syntax to use for this job
        """
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        # No edits on protected factoids
        if await self.check_protected(interaction, factoid):
            return

        factoid_job = await self.read_factoid_job_by_channel(
            guild=interaction.guild,
            factoid_data_id=factoid.factoid_data_id,
            channel=channel,
        )

        if not factoid_job:
            await self.respond_error_embed(
                interaction,
                f"The factoid `{factoid_name}` doesn't have a job in {channel.mention}!",
            )
            return

        await interaction.response.defer()
        # We need to update the database entry and reschedule the job
        await self.unschedule_job(factoid_job)
        await factoid_job.update(cron=cron).apply()
        await self.register_job(factoid_job)

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.handle_factoid_edit(interaction.guild, factoid)

        embed = auxiliary.prepare_confirm_embed(
            f"The loop in {channel.mention} for factoid `{factoid_name}` was edited successfully"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.check(has_admin_factoids_role)
    @factoid_loop_commands.command(
        name="refresh",
        description="Refreshes all the scheduled factoid loops for this guild",
    )
    async def factoid_loop_refresh_command(
        self: Self,
        interaction: discord.Interaction,
    ) -> None:
        """This is designed to cancel and reschedule all jobs in the guild, for debug purposes

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
        """
        jobs = await self.get_all_jobs_for_guild(interaction.guild)
        if not jobs:
            await self.respond_error_embed(
                interaction, "There are no configured jobs for this guild"
            )
            return

        await interaction.response.defer()
        for job in jobs:
            await self.unschedule_job(job)
            await self.register_job(job)

        embed = auxiliary.prepare_confirm_embed(
            f"Refreshed {len(jobs)} job{"s" if len(jobs)>1 else ""} in this guild"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="property",
        description="Modifies properites of the given factoid",
    )
    @app_commands.autocomplete(factoid_name=property_factoid_autocomplete)
    async def factoid_property_command(
        self: Self,
        interaction: discord.Interaction,
        factoid_name: str,
        property: Properties,
        set_value: bool,
    ) -> None:
        factoid_name = factoid_name.lower()
        # Make sure the factoid is valid
        factoid = await self.get_valid_factoid(
            interaction=interaction, factoid_name=factoid_name
        )
        if not factoid:
            return

        # No edits on protected factoids, unless we are modifying the protected flag
        if property != Properties.PROTECTED and await self.check_protected(
            interaction, factoid
        ):
            return

        # Check if the property is already set to the requested value
        currently_set = bool(factoid.flags & property)

        if currently_set == set_value:
            state = "enabled" if set_value else "disabled"

            await self.respond_error_embed(
                interaction,
                f"The property `{property.name.lower()}` is already {state} for `{factoid_name}`!",
            )
            return

        # Apply the property change
        if set_value:
            new_flags = factoid.flags | property
        else:
            new_flags = factoid.flags & ~property

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.handle_factoid_edit(
            interaction.guild,
            factoid,
        )

        factoid = await self.update_factoid_data(
            guild=interaction.guild,
            factoid_data_id=factoid.factoid_data_id,
            flags=new_flags,
        )

        state = "enabled" if set_value else "disabled"

        embed = auxiliary.prepare_confirm_embed(
            message=(
                f"The property `{property.name.lower()}` was successfully "
                f"{state} for `{factoid_name}`!"
            )
        )

        await interaction.response.send_message(embed=embed)

    @factoid_app_group.command(
        name="search",
        description="Searches for factoids where the message or json match the query",
        extras={"ephemeral_error": True},
    )
    async def factoid_search_command(
        self: Self,
        interaction: discord.Interaction,
        query: str,
    ) -> None:
        """This will search all facatoids in the guild and display any that match the search query
        This will filter out hidden factoids

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
        """
        query = query.lower()
        if len(query) <= 3:
            await self.respond_error_embed(
                interaction, "The minimum search query length is 4 characters"
            )
            return

        await interaction.response.defer(ephemeral=True)
        all_factoids = await self.get_all_factoids_for_guild(guild=interaction.guild)

        matching_factoids: list[FactoidView] = []

        for factoid in all_factoids:
            # Filter hidden factoids
            if factoid.flags & Properties.HIDDEN:
                continue

            if query in factoid.message.lower() or query in factoid.json_string.lower():
                matching_factoids.append(factoid)

        if not matching_factoids:
            await self.respond_error_embed(
                interaction,
                f"No factoids matched the query `{query}`!",
            )
            return

        title = f"Found {len(matching_factoids)} matching factoid{'s' if len(matching_factoids) != 1 else ''}"

        factoids = matching_factoids[:50]
        embeds: list[discord.Embed] = []

        for i in range(0, len(factoids), 5):
            chunk = factoids[i : i + 5]

            lines = [
                f"`[{', '.join(factoid.calls)}]`: {factoid.message[:30]}"
                for factoid in chunk
            ]

            embed = discord.Embed(
                title=title, description="\n".join(lines), color=discord.Color.green()
            )

            embeds.append(embed)

        view = ui.PaginateView()
        await view.send(
            interaction.channel, interaction.user, embeds, interaction, True
        )

    @factoid_app_group.command(
        name="top",
        description="Displays the top 10 factoids by number of times called",
    )
    async def factoid_top_command(
        self: Self,
        interaction: discord.Interaction,
    ) -> None:
        """This will display the most commonly called factoids in this guild
        It will ignore hidden factoids

        Args:
            interaction (discord.Interaction): The interaction that triggered this command
        """

        all_factoids = await self.get_all_factoids_for_guild(guild=interaction.guild)

        visible_factoids: list[FactoidView] = []

        for factoid in all_factoids:
            # Ignore hidden factoids
            if factoid.flags & Properties.HIDDEN:
                continue

            visible_factoids.append(factoid)

        if not visible_factoids:
            await self.respond_error_embed(
                interaction,
                "There are no factoids in this guild!",
            )
            return

        sorted_factoids = sorted(
            visible_factoids,
            key=lambda factoid: factoid.times_called,
            reverse=True,
        )

        top_factoids = sorted_factoids[:10]

        lines: list[str] = []

        for index, factoid in enumerate(top_factoids, start=1):
            lines.append(
                f"{index}. `[{', '.join(factoid.calls)}]` - {factoid.times_called} call{'s' if factoid.times_called != 1 else ''}"
            )

        embed = discord.Embed(
            title=f"Top {len(top_factoids)} factoid{'s' if len(top_factoids) != 1 else ''}",
            description="\n".join(lines),
        )
        embed.color = discord.Color.blue()

        await interaction.response.send_message(embed=embed)

    # TODO: Legacy prefix factoid calls
    # TODO: Add guild config to control whether prefix factoids are enabled. Default to FALSE


class ButtonView(discord.ui.View):
    """The class to hold the view for the delete button on /factoid call

    Args:
        author_id (int): The ID of the author of the factoid
    """

    # At a point in which we migrate to components, this view should take over sending and processing the embed/plaintext factiods
    # A new view entirely designed around components should exist to send those factoids

    def __init__(self: Self, author_id: int, factoid: FactoidView) -> None:
        super().__init__(timeout=600)
        self.author_id = author_id
        self.factoid: FactoidView = factoid
        self.message: discord.Message | None = None

    async def on_timeout(self: Self) -> None:
        """Is called after the timeout, with the goal of disabling the buttons from the message"""

        for child in self.walk_children():
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            await self.message.edit(view=self)

        # Be memory safe and clear these objects
        self.factoid = None
        self.message = None

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_button(
        self: Self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """The function called when the delete button is pressed

        Args:
            interaction (discord.Interaction): The interaction that pressed the button
            button (discord.ui.Button): The button object itself
        """

        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the original caller can delete this message.",
                ephemeral=True,
            )
            return

        if interaction.message:
            await interaction.message.delete()

    @discord.ui.button(
        label="I see nothing", style=discord.ButtonStyle.blurple, emoji="👁️"
    )
    async def cant_see_button(
        self: Self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """The function called when the see nothing button is pressed

        Args:
            interaction (discord.Interaction): The interaction that pressed the button
            button (discord.ui.Button): The button object itself
        """
        await interaction.response.send_message(
            content=self.factoid.message, ephemeral=True
        )

        # Tell user how to enable embeds
        await interaction.followup.send(
            f"To see these messages in the future, consider enabling embeds: <https://rtech.support/meta/discord-embeds/>",
            ephemeral=True,
        )

    @discord.ui.button(label="Save to DMs", style=discord.ButtonStyle.green, emoji="💬")
    async def send_to_dm_button(
        self: Self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """The function called when the save to DMs button is pressed

        Args:
            interaction (discord.Interaction): The interaction that pressed the button
            button (discord.ui.Button): The button object itself
        """
        try:
            await interaction.user.send(
                content=interaction.message.content, embeds=interaction.message.embeds
            )
        except discord.Forbidden:
            embed = auxiliary.prepare_deny_embed(
                "It appears you have DMs closed. I can't send you this factoid"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(
            "I sent a copy of this factoid to your DMs", ephemeral=True
        )


class FactoidModal(discord.ui.Modal):
    """A Modal that contains information to make or edit a factoid
    This has the user fill in plaintext content, upload an embed json file
    And select default properties for the factoid

    Args:
        factoid (str): The name of the factoid, to display in the title

    Attributes:
        plaintext (discord.ui.Label): The plaintext representation of the factoid
        embed (discord.ui.Label): The json file attachment of the factoid
        properties (discord.ui.Label): The properties of the factoid, such as hidden or disabled
    """

    def __init__(
        self,
        factoid_name: str,
        edit_mode: bool,
        factoid: FactoidView | None = None,
    ) -> None:
        super().__init__(
            title=(
                f"Editing factoid {factoid_name}"
                if edit_mode
                else f"Creating factoid {factoid_name}"
            )[:45]
        )

        self.plaintext = discord.ui.Label(
            text="Plaintext:",
            component=discord.ui.TextInput(
                style=discord.TextStyle.long,
                required=True,
                default=factoid.message if factoid else None,
            ),
        )

        self.add_item(self.plaintext)

        if edit_mode:
            self.json_action = discord.ui.Label(
                text="JSON Action:",
                component=discord.ui.RadioGroup(
                    required=True,
                    options=[
                        discord.RadioGroupOption(
                            label="Keep Existing",
                            value="keep",
                            default=True,
                        ),
                        discord.RadioGroupOption(
                            label="Remove Existing",
                            value="remove",
                        ),
                        discord.RadioGroupOption(
                            label="Replace Existing",
                            value="replace",
                        ),
                    ],
                ),
            )

            self.add_item(self.json_action)

        self.embed = discord.ui.Label(
            text="Embed JSON:",
            component=discord.ui.FileUpload(required=False),
        )

        self.add_item(self.embed)

        if not edit_mode:
            property_options = []

            for prop in Properties:
                property_options.append(
                    discord.CheckboxGroupOption(
                        label=prop.name.title(),
                        value=str(prop),
                        default=(bool(factoid.flags & prop) if factoid else False),
                    )
                )
            self.properties = discord.ui.Label(
                text="Properties:",
                component=discord.ui.CheckboxGroup(
                    max_values=len(property_options),
                    required=False,
                    options=property_options,
                ),
            )

            self.add_item(self.properties)

    async def on_submit(self: Self, interaction: discord.Interaction) -> None:
        """What happens when the form has been successfully submitted

        Args:
            interaction (discord.Interaction): The interaction that caused the form to be show
        """
        await interaction.response.defer()
        return


class InfoEmbedButtons(discord.ui.View):
    def __init__(
        self: Self, author_id: int, factoid: FactoidView, cog: FactoidManager
    ) -> None:
        super().__init__(timeout=600)
        self.author_id = author_id
        self.factoid: FactoidView = factoid
        self.cog = cog
        self.message: discord.Message | None = None

    async def on_timeout(self: Self) -> None:
        """Is called after the timeout, with the goal of disabling the buttons from the message"""

        for child in self.walk_children():
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        if self.message:
            await self.message.edit(view=self)

        # Be memory safe and clear these objects
        self.factoid = None
        self.message = None
        self.cog = None

    @discord.ui.button(label="Show JSON file", style=discord.ButtonStyle.blurple)
    async def show_json(
        self: Self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """The function called when the show json file button is pressed

        Args:
            interaction (discord.Interaction): The interaction that pressed the button
            button (discord.ui.Button): The button object itself
        """
        json_file = self.cog.create_json_file(self.factoid)
        await interaction.response.send_message(file=json_file, ephemeral=True)

    @discord.ui.button(label="Show embed", style=discord.ButtonStyle.blurple)
    async def show_embed(
        self: Self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """The function called when the show embed is pressed

        Args:
            interaction (discord.Interaction): The interaction that pressed the button
            button (discord.ui.Button): The button object itself
        """
        embed, _ = await self.cog.generate_sendable_factoid(
            interaction.guild, self.factoid
        )
        if not embed:
            await self.cog.respond_error_embed(
                "The embed for this factoid could not be generated"
            )

        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.HTTPException:
            await self.cog.respond_error_embed(
                "The embed for this factoid could not be sent"
            )
