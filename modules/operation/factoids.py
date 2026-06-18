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

import discord
import yaml
from aiohttp.client_exceptions import InvalidURL
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
    for name in check_roles:
        factoid_role = discord.utils.get(guild.roles, name=name)
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


class Properties(Enum):
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


# TODO: Update/remake all doc strings
# TODO: create/edit need to have duplicate json file to string code generic shared function
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
        # TODO: Factoid all cache
        self.factoid_cache: dict[str, FactoidView] = {}

        # Register the loop callback into APScheduler
        self.bot.scheduler.register_task(
            "factoid_loop",
            self.execute_job,
        )

        # On bot startup, start all jobs
        await self.startup_jobs()

    # LOOP STUFF

    async def startup_jobs(self: Self) -> None:
        all_jobs = await self.get_all_global_jobs()
        for job in all_jobs:
            await self.register_job(job)

    async def register_job(self: Self, job: bot.models.FactoidJob) -> None:
        guild = self.bot.get_guild(int(job.guild))
        # Do not register the job if extension is disabled
        if not self.extension_enabled(guild=guild):
            return

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

        # Stop execution if factoids has been disabled
        if not self.extension_enabled(guild=guild):
            return

        job_data = await self.read_factoid_job_by_id(guild, factoid_job_id)
        if not job_data:
            return
        factoid = await self.get_factoid_view_by_id(guild, job_data.factoid_data_id)
        if not factoid:
            return

        # If the FactoidJob and FactoidData entry both exist, the job is valid. We reschedule here to prevent a different error causing the job to be shadow cancelled
        await self.register_job(job_data)

        channel = self.bot.get_channel(int(job_data.channel))
        if not channel:
            return

        # Check if factoid is disabled. If so, don't send it
        if factoid.flags & Properties.DISABLED.value:
            return

        # Check if factoid is restricted. If so, check if we can call it
        if (
            factoid.flags & Properties.RESTRICTED.value
            and not self.can_channel_send_restricted(channel)
        ):
            return

        embed, plaintext_content = await self.generate_sendable_factoid(guild, factoid)

        # Log in the background
        asyncio.create_task(
            self.log_factoid_send(
                guild=guild,
                channel=channel,
                sender=guild.me,
                factoid=factoid,
            )
        )

        embed_sent = False
        if embed:
            try:
                # Attempt to send the message with the embed in it
                sent_message = await channel.send(embed=embed)
                embed_sent = True
            # If something breaks, also log it
            except discord.errors.HTTPException as exception:
                # TODO: This logging (and /factoid calls copy) can be done in the background, and in a separate function
                log_channel = configuration.get_config_entry(
                    guild.id, "core_logging_channel"
                )
                await self.bot.logger.send_log(
                    message=(
                        f"Unable to send embed for factoid `[{", ".join(factoid.calls)}]`, "
                        "sending fallback."
                    ),
                    level=LogLevel.ERROR,
                    context=LogContext(guild=guild, channel=channel),
                    channel=log_channel,
                    exception=exception,
                )

        # Either no embed exists, or the embed failed to send for some reason.
        # We will send the plaintext content of the factoid in this case
        if not embed_sent:
            content = plaintext_content.strip()
            if len(content) > 2000:
                return

            sent_message = await channel.send(content=content)
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
        """Remove all scheduled APScheduler entries for a factoid job."""
        # TODO: Check for task name
        for scheduled_job in await self.bot.scheduler.get_upcoming_tasks():
            payload = scheduled_job["payload"]

            if (
                payload.get("job_id") == job.factoid_job_id
                and str(payload.get("guild").id) == job.guild
            ):
                self.bot.scheduler.scheduler.remove_job(scheduled_job["job_id"])

    # DATABASE CALLS
    # TODO: Re-evaluate the use of these functions

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

    async def delete_factoid_data(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
    ) -> None:
        """Deletes factoid data from the database
        This does not impact factoid jobs or factoid calls

        Args:
            guild (discord.Guild): The guild the factoid data is stored in
            factoid_data_id (int): The ID of the data entry to delete
        """

        await self.bot.models.FactoidData.delete.where(
            (self.bot.models.FactoidData.guild == str(guild.id))
            & (self.bot.models.FactoidData.factoid_data_id == factoid_data_id)
        ).gino.status()

    async def get_all_factoid_calls(
        self: Self,
        guild: discord.Guild,
    ) -> list[bot.models.FactoidCall]:
        """This gets all FactoidCall database entries for a given guild

        Args:
            guild (discord.Guild): The guild to search for

        Returns:
            list[bot.models.FactoidCall]: The list of raw database entries
        """
        return await self.bot.models.FactoidCall.query.where(
            self.bot.models.FactoidCall.guild == str(guild.id)
        ).gino.all()

    async def create_factoid_data(
        self: Self,
        guild: discord.Guild,
        message: str,
        json_string: str,
        flags: int,
    ) -> bot.models.FactoidData:
        """Creates a new factoid data entry in the table
        This will not create a call to this factoid

        Args:
            guild (discord.Guild): The guild to create this factoid for
            message (str): The plaintext version of the factoid
            json_string (str): The json for this factoid
            flags (int): The property binary flags for this factoid

        Returns:
            bot.models.FactoidData: The newly created database entry
        """

        return await self.bot.models.FactoidData.create(
            guild=str(guild.id),
            message=message,
            json_string=json_string,
            flags=flags,
            times_called=0,
        )

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

    async def create_factoid_job(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
        channel: discord.abc.GuildChannel,
        cron: str,
    ) -> bot.models.FactoidJob:
        """Creates a new FactoidJob entry in the table

        Args:
            guild (discord.Guild): The guild to create this factoid for
            message (str): The plaintext version of the factoid
            json_string (str): The json for this factoid
            flags (int): The property binary flags for this factoid

        Returns:
            bot.models.FactoidJob: The newly created database entry
        """

        return await self.bot.models.FactoidJob.create(
            guild=str(guild.id),
            factoid_data_id=factoid_data_id,
            channel=str(channel.id),
            cron=cron,
        )

    async def read_factoid_job_by_id(
        self: Self,
        guild: discord.Guild,
        factoid_job_id: int,
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
            & (self.bot.models.FactoidJob.factoid_job_id == factoid_job_id)
        ).gino.first()

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

    async def get_all_global_jobs(self: Self) -> list[bot.models.FactoidJob]:
        return await self.bot.models.FactoidJob.query.gino.all()

    async def get_all_jobs_for_guild(
        self: Self, guild: discord.Guild
    ) -> list[bot.models.FactoidJob]:
        return await self.bot.models.FactoidJob.query.where(
            (self.bot.models.FactoidJob.guild == str(guild.id))
        ).gino.all()

    async def get_all_factoid_data(
        self: Self,
        guild: discord.Guild,
    ) -> list[bot.models.FactoidData]:
        """This gets all FactoidData database entries for a given guild

        Args:
            guild (discord.Guild): The guild to search for

        Returns:
            list[bot.models.FactoidData]: The list of raw database entries
        """
        return await self.bot.models.FactoidData.query.where(
            self.bot.models.FactoidData.guild == str(guild.id)
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

    async def get_factoid_jobs_by_channel(
        self: Self,
        guild: discord.Guild,
        factoid_data_id: int,
        channel: discord.abc.GuildChannel,
    ) -> list[bot.models.FactoidJob]:
        """Returns all jobs pointing to a factoid in a specific channel."""

        return await self.bot.models.FactoidJob.query.where(
            (self.bot.models.FactoidJob.guild == str(guild.id))
            & (self.bot.models.FactoidJob.factoid_data_id == factoid_data_id)
            & (self.bot.models.FactoidJob.channel == str(channel.id))
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

    async def delete_factoid_call_by_name(
        self: Self,
        guild: discord.Guild,
        name: str,
    ) -> bool:
        """
        Deletes a factoid call.
        If it was the last call, deletes the underlying factoid data too.
        Returns True if anything was deleted.
        """

        call = await self.get_factoid_call(
            guild=guild,
            name=name,
        )

        if not call:
            return False

        factoid_data_id = call.factoid_data_id

        # delete the call first
        await self.delete_factoid_call(
            guild=guild,
            name=name,
        )

        # check remaining calls
        remaining_calls = await self.get_factoid_calls_by_factoid_id(
            guild=guild,
            factoid_data_id=factoid_data_id,
        )

        if not remaining_calls:
            await self.delete_factoid_data(
                guild=guild,
                factoid_data_id=factoid_data_id,
            )

        return True

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

        # TODO: This needs to be re-written

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
        factoid_data = await self.get_all_factoid_data(guild)
        factoid_calls = await self.get_all_factoid_calls(guild)

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

    async def update_edit_time_for_factoid(
        self: Self, guild: discord.Guild, factoid: FactoidView
    ) -> None:
        """Sets the edit time of the factoid to now

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
        # TODO: Include properties in the yaml file
        # We should never be here, but just in case
        if not factoids:
            return None

        output_data = []

        for index, factoid in enumerate(factoids):

            calls = factoid.calls

            data = {
                "calls": calls,
                "message": factoid.message,
                "embed": bool(factoid.json_string),
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
            await self.bot.logger.send_log(
                message=(
                    f"Unable to make embed for factoid `[{", ".join(factoid.calls)}]`, "
                    "sending fallback."
                ),
                level=LogLevel.ERROR,
                channel=configuration.get_config_entry(
                    guild.id,
                    "core_logging_channel",
                ),
                context=LogContext(
                    guild=guild,
                ),
                exception=exception,
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
                f"Sending factoid: `[{", ".join(factoid.calls)}]` (triggered by {sender} in"
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

    # AUTOFILL

    async def factoid_autocomplete(
        self: Self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Suggests factoids for autofill for commands that need autofilled factoids

        Args:
            interaction (discord.Interaction): The interaction calling the factoids
            current (str): The current string value of the factoid argument

        Returns:
            list[app_commands.Choice[str]]: The list of suggestions
        """
        # TODO: Filter disabled/restricted factoids

        guild = interaction.guild
        if guild is None:
            return []

        current = current.lower()

        factoids = (
            await self.bot.models.FactoidCall.query.where(
                (self.bot.models.FactoidCall.guild == str(guild.id))
                & (self.bot.models.FactoidCall.name.ilike(f"{current}%"))
            )
            .order_by(self.bot.models.FactoidCall.name)
            .limit(25)
            .gino.all()
        )

        return [
            app_commands.Choice(
                name=factoid.name,
                value=factoid.name,
            )
            for factoid in factoids
        ]

    # COMMANDS

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="alias",
        description="Creates an alias for an existing factoid call",
    )
    @app_commands.autocomplete(existing_factoid=factoid_autocomplete)
    async def factoid_alias_command(
        self: Self,
        interaction: discord.Interaction,
        existing_factoid: str,
        new_factoid: str,
    ) -> None:
        existing_factoid = existing_factoid.lower()
        new_factoid = new_factoid.lower()
        if not self.check_valid_name(new_factoid):
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid name `{new_factoid}` is invalid and cannot be used!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if new_factoid == existing_factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"You cannot alias a factoid to itself!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=existing_factoid
        )

        # We can't alias a factoid if it doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{existing_factoid}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # No aliases on protected factoids
        if factoid.flags & Properties.PROTECTED.value:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{existing_factoid}` is protected and cannot be edited."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        new_factoid_db = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=new_factoid
        )

        # If the existing and new calls already point to the same factoid, there is nothing to do
        if new_factoid_db and factoid.factoid_data_id == new_factoid_db.factoid_data_id:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{new_factoid}` is already an alias of `{existing_factoid}`."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # If the new_factoid already exists but point elsewhere, we need to ask the user for confirmation
        if new_factoid_db:
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
                embed = auxiliary.prepare_deny_embed(
                    message=f"The factoid `{new_factoid}` was not replaced.",
                )
                interaction.followup.send(embed=embed)
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
        await self.update_edit_time_for_factoid(interaction.guild, factoid)

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
        # TODO: Caching - MAYBE
        # TODO: Check if guild has zero factoids, make special error
        # Caching here would require us to build a guild:properties_flags key

        all_factoids = await self.get_all_factoids_for_guild(guild=interaction.guild)

        # Property filters only avaiable to manage roles
        if factoid_property or show_all:
            await has_given_factoids_role(
                interaction.guild,
                interaction.user,
                configuration.get_config_entry(
                    interaction.guild.id, "factoids_manage_roles"
                ),
            )

        # Top priority is abiding by show_all
        # If not but a specific property is requested, show that
        # Otherwise, show a normal filtered list, no hidden, no disabled, no restricted
        if show_all:
            filtered_factoids = all_factoids
        elif factoid_property:
            filtered_factoids = [
                factoid
                for factoid in all_factoids
                if factoid.flags & factoid_property.value
            ]
        else:
            # Determine whether restricted factoids should be visible here
            should_show_restricted = self.can_channel_send_restricted(
                interaction.channel,
            )

            filtered_factoids = [
                factoid
                for factoid in all_factoids
                if (
                    # Never show hidden factoids normally
                    not (factoid.flags & Properties.HIDDEN.value)
                    # Never show disabled factoids normally
                    and not (factoid.flags & Properties.DISABLED.value)
                    # Restricted factoids depend on channel
                    and (
                        should_show_restricted
                        or not (factoid.flags & Properties.RESTRICTED.value)
                    )
                )
            ]

        filtered_factoids.sort(key=lambda factoid: factoid.calls[0])
        if not filtered_factoids:
            embed = auxiliary.prepare_deny_embed(
                "No factoids could be found matching your filter"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # If the linx server isn't configured, we must make it a file
        if not self.bot.file_config.api.api_url.linx:
            force_file = True

        await interaction.response.defer(ephemeral=True)

        factoid_all = await self.build_factoid_all(
            guild=interaction.guild, factoids=filtered_factoids, use_file=force_file
        )

        if not factoid_all:
            embed = auxiliary.prepare_deny_embed(
                "Something went wrong generating the list of factoids"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # If we know it's a file, or it's fallen back to a file, send it as a file
        if isinstance(factoid_all, discord.File):
            await interaction.followup.send(file=factoid_all, ephemeral=True)
            return

        embed = auxiliary.prepare_confirm_embed(factoid_all)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @factoid_app_group.command(
        name="call",
        description="Calls a factoid from the database and sends it publicy in the channel.",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
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
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` couldn't be found"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check if factoid is disabled. If so, don't send it
        if factoid.flags & Properties.DISABLED.value:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is disabled."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check if factoid is restricted. If so, check if we can call it
        if (
            factoid.flags & Properties.RESTRICTED.value
            and not self.can_channel_send_restricted(interaction.channel)
        ):
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is restricted and not allowed in this channel."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
                log_channel = configuration.get_config_entry(
                    interaction.guild.id, "core_logging_channel"
                )
                await self.bot.logger.send_log(
                    message=(
                        f"Unable to send embed for factoid `{factoid_name}`, "
                        "sending fallback."
                    ),
                    level=LogLevel.ERROR,
                    context=LogContext(
                        guild=interaction.guild, channel=interaction.channel
                    ),
                    channel=log_channel,
                    exception=exception,
                )

        # Either no embed exists, or the embed failed to send for some reason.
        # We will send the plaintext content of the factoid in this case
        if not embed_sent:
            content += f" {plaintext_content}"
            content = content.strip()
            if len(content) > 2000:
                embed = auxiliary.prepare_deny_embed(
                    message=f"The factoid `{factoid_name}` is too long and cannot be sent on discord."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
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
    )
    async def factoid_create_command(
        self: Self, interaction: discord.Interaction, factoid_name: str
    ) -> None:
        factoid_name = factoid_name.lower()
        # Only ever attempt to add a factoid if it doesn't exist
        # TODO: Change this to reading factoid, per the standard
        if await self.read_factoid_call(guild=interaction.guild, name=factoid_name):
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` already exists"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not self.check_valid_name(factoid_name):
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid name `{factoid_name}` is invalid and cannot be used!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        form = FactoidModal(factoid_name, edit_mode=False)
        await interaction.response.send_modal(form)
        await form.wait()

        if not self.check_valid_message(form.plaintext.component.value):
            embed = auxiliary.prepare_deny_embed(
                message="The message content is invalid and cannot be used!"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        embed_json_string = ""

        if form.embed.component.values:
            embed_file: discord.Attachment = form.embed.component.values[0]

            if not embed_file.filename.endswith(".json"):
                embed = auxiliary.prepare_deny_embed(
                    message="I don't recognize your upload as a JSON file.",
                )
                await interaction.followup.send(embed=embed)
                return

            try:
                json_bytes = await embed_file.read()
                attachment_json = json.loads(json_bytes.decode("UTF-8"))
                embed_json_string = json.dumps(attachment_json)

            except Exception:
                embed = auxiliary.prepare_deny_embed(
                    message="I couldn't parse the uploaded JSON file.",
                )
                await interaction.followup.send(embed=embed)
                return

        selected = set(form.properties.component.values)

        property_binary = sum(int(value) for value in selected)

        factoid = await self.create_factoid_data(
            guild=interaction.guild,
            message=form.plaintext.component.value,
            json_string=embed_json_string,
            flags=property_binary,
        )

        await self.create_factoid_call(
            guild=interaction.guild,
            name=factoid_name,
            factoid_data_id=factoid.factoid_data_id,
        )

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
                await interaction.followup.send(
                    f"The embed you uploaded failed: {exc}", ephemeral=True
                )

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="dealias",
        description="Deletes an alias for an existing factoid call",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
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
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )

        # We can't dealias a factoid if it doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # No edits on protected factoids
        if factoid.flags & Properties.PROTECTED.value:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is protected and cannot be edited."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Only allowed to dealias if this wouldn't require deleting the entire factoid
        if len(factoid.calls) == 1:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` has no other aliases."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await self.delete_factoid_call(guild=interaction.guild, name=factoid_name)
        factoid.calls.remove(factoid_name)
        remaining_aliases = ", ".join(factoid.calls)
        embed = auxiliary.prepare_confirm_embed(
            message=f"The factoid alias `{factoid_name}` was removed. Remaining aliases: `{remaining_aliases}`"
        )

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.update_edit_time_for_factoid(interaction.guild, factoid)

        await interaction.response.send_message(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="delete",
        description="Deletes a factoid, all aliases and all jobs",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
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
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )

        # We can't delete a factoid if it doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # No edits on protected factoids
        if factoid.flags & Properties.PROTECTED.value:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is protected and cannot be edited."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        confirmation_response = await self.confirm_factoid_deletion(
            interaction=interaction,
            display_message=f"Are you sure you want to delete the factoid `[{", ".join(factoid.calls)}]`?",
            channel=interaction.channel,
            author=interaction.user,
        )
        if confirmation_response == ui.ConfirmResponse.TIMEOUT:
            return
        elif confirmation_response == ui.ConfirmResponse.DENIED:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` was not deleted.",
            )
            interaction.followup.send(embed=embed)
            return

        await self.delete_factoid_data_by_id(interaction.guild, factoid.factoid_data_id)

        # Remove factoid from cache after deleting
        self.remove_from_cache(interaction.guild, factoid)

        embed = auxiliary.prepare_confirm_embed(
            f"The factoid `[{", ".join(factoid.calls)}]` was deleted"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_app_group.command(
        name="edit",
        description="Edits an existing factoids message, embed or properties",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
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
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )

        # We can't edit a factoid if it doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # No edits on protected factoids
        if factoid.flags & Properties.PROTECTED.value:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is protected and cannot be edited."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        form = FactoidModal(factoid_name, edit_mode=True, factoid=factoid)
        await interaction.response.send_modal(form)
        await form.wait()

        if not self.check_valid_message(form.plaintext.component.value):
            embed = auxiliary.prepare_deny_embed(
                message="The message content is invalid and cannot be used!"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
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
                embed = auxiliary.prepare_deny_embed(
                    message="The json file was requested to be replaced, but no file was uploaded. No edits were made."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            embed_file: discord.Attachment = form.embed.component.values[0]

            if not embed_file.filename.endswith(".json"):
                embed = auxiliary.prepare_deny_embed(
                    message="I don't recognize your upload as a JSON file. No edits were made.",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                json_bytes = await embed_file.read()
                attachment_json = json.loads(json_bytes.decode("UTF-8"))
                embed_json_string = json.dumps(attachment_json)

            except Exception:
                embed = auxiliary.prepare_deny_embed(
                    message="I couldn't parse the uploaded JSON file. No edits were made.",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        # If the factoid was not edited, do nothing
        if not show_embed and not show_plaintext:
            embed = auxiliary.prepare_deny_embed(
                message="It doesn't appear any edits were made to this factoid. No edits were made.",
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.update_edit_time_for_factoid(interaction.guild, factoid)

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
                await interaction.followup.send(
                    f"The embed you uploaded failed: {exc}", ephemeral=True
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
        # TODO: Will need to clear factoid all cache when it exists
        for entry in list(self.factoid_cache.keys()):
            if entry.startswith(str(interaction.guild.id)):
                del self.factoid_cache[entry]

        embed = auxiliary.prepare_confirm_embed("Factoid cache for this guild cleared")
        await interaction.response.send_message(embed=embed)

    @factoid_app_group.command(
        name="info",
        description="Gets information about a factoid and displays it to the user.",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
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
        # TODO: Add embed/json buttons

        factoid_name = factoid_name.lower()
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )

        # We can't get info from a factoid that doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Info about `{factoid_name}`", description=factoid.message
        )
        embed.color = discord.Color.blue()
        embed.add_field(name="Calls", value=f"`[{', '.join(factoid.calls)}]`")
        embed.add_field(name="Time called", value=factoid.times_called)
        embed.add_field(name="Embed", value=bool(factoid.json_string))

        # Handle properties different to convert from into to string
        properties_str = (
            ", ".join(
                prop.name.lower() for prop in Properties if factoid.flags & prop.value
            )
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

        await interaction.response.send_message(embed=embed)

    @factoid_app_group.command(
        name="json",
        description="Gets the json file for the embed of this factoid",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
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
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )

        # We can't get info from a factoid that doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not factoid.json_string:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't have any embed configured!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
            embed = auxiliary.prepare_deny_embed(
                "There are no configured jobs for this guild"
            )
            interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(title=f"Factoid loop for {interaction.guild.name}")
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
        description="Creates an new factoid loop job in the specified channel",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
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
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )

        # We can't edit a factoid if it doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # No edits on protected factoids
        if factoid.flags & Properties.PROTECTED.value:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is protected and cannot be edited."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # We can only have 1 factoid have a job per channel
        existing_job = await self.get_factoid_jobs_by_channel(
            interaction.guild, factoid.factoid_data_id, channel
        )
        if existing_job:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` already has a job in {channel.mention}."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # TODO: Validate cron syntax
        job_data = await self.create_factoid_job(
            guild=interaction.guild,
            factoid_data_id=factoid.factoid_data_id,
            channel=channel,
            cron=cron,
        )
        # TODO: Catch ValueError here
        await self.register_job(job_data)

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.update_edit_time_for_factoid(interaction.guild, factoid)

        embed = auxiliary.prepare_confirm_embed(
            f"The loop in {channel.mention} for factoid {factoid_name} was created successfully"
        )
        await interaction.followup.send(embed=embed)

    @app_commands.check(has_manage_factoids_role)
    @factoid_loop_commands.command(
        name="delete",
        description="Deletes an existing factoid loop job based on name and channel",
    )
    @app_commands.autocomplete(factoid_name=factoid_autocomplete)
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
        factoid = await self.get_factoid_view_by_name(
            guild=interaction.guild, name=factoid_name
        )

        # We can't edit a factoid if it doesn't exist
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't exist!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # No edits on protected factoids
        if factoid.flags & Properties.PROTECTED.value:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` is protected and cannot be edited."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        factoid_job = await self.read_factoid_job_by_channel(
            guild=interaction.guild,
            factoid_data_id=factoid.factoid_data_id,
            channel=channel,
        )

        if not factoid_job:
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_name}` doesn't have a job in {channel.mention}!"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # We need to cancel the job in APScheduler and delete the database entry
        await self.unschedule_job(factoid_job)
        await factoid_job.delete()

        # Update the factoid edit time
        # This will also remove the factoid from the cache
        await self.update_edit_time_for_factoid(interaction.guild, factoid)

        embed = auxiliary.prepare_confirm_embed(
            f"The loop in {channel.mention} for factoid `{factoid_name}` was deleted successfully"
        )
        await interaction.response.send_message(embed=embed)

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
            embed = auxiliary.prepare_deny_embed(
                "There are no configured jobs for this guild"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()
        for job in jobs:
            await self.unschedule_job(job)
            await self.register_job(job)

        embed = auxiliary.prepare_confirm_embed(
            f"Refreshed {len(jobs)} job{"s" if len(jobs)>1 else ""} in this guild"
        )
        await interaction.followup.send(embed=embed)


class ButtonView(discord.ui.View):
    # TODO: Migrate to LayoutView
    # TODO: Make this entirely in charge of displaying factoids for factoid call and factoid loop jobs
    """The class to hold the view for the delete button on /factoid call

    Args:
        author_id (int): The ID of the author of the factoid
    """

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
                        value=str(prop.value),
                        default=(
                            bool(factoid.flags & prop.value) if factoid else False
                        ),
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
