"""Module for defining the advanced bot methods."""
import asyncio
import collections
import time

import munch

from .data import DataBot


class AdvancedBot(DataBot):
    """Advanced extension bot with per-guild config access."""

    GUILD_CONFIG_COLLECTION = "guild_config"
    CONFIG_RECEIVE_WARNING_TIME_MS = 1000

    def __init__(self, *args, **kwargs):
        self.guild_config_collection = None
        self.guild_config_cache = collections.defaultdict(dict)
        self.guild_config_lock = asyncio.Lock()
        super().__init__(*args, prefix=self.get_prefix, **kwargs)
        self.loop.create_task(self.reset_config_cache())

    async def get_prefix(self, message):
        """Gets the appropriate prefix for a command.

        parameters:
            message (discord.Message): the message to check against
        """
        guild_config = await self.get_context_config(guild=message.guild)
        return getattr(
            guild_config, "command_prefix", self.file_config.main.default_prefix
        )

    async def reset_config_cache(self):
        """Deletes the guild config cache on a periodic basis."""
        while True:
            await asyncio.sleep(self.file_config.main.config_cache_reset)
            await self.logger.info("Resetting guild config cache")
            self.guild_config_cache = collections.defaultdict(dict)

    async def get_context_config(
        self, ctx=None, guild=None, create_if_none=True, get_from_cache=True
    ):
        """Gets the appropriate config for the context.

        parameters:
            ctx (discord.ext.Context): the context of the config
            guild (discord.Guild): the guild associated with the config (provided instead of ctx)
            create_if_none (bool): True if the config should be created if not found
            get_from_cache (bool): True if the config should be fetched from the cache
        """
        start = time.time()

        if ctx:
            guild_from_ctx = getattr(ctx, "guild", None)
            lookup = guild_from_ctx.id if guild_from_ctx else "dmcontext"
        elif guild:
            lookup = guild.id
        else:
            return None

        lookup = str(lookup)

        config_ = None

        if get_from_cache:
            config_ = self.guild_config_cache[lookup]

        if not config_:
            # locking prevents duplicate configs being made
            async with self.guild_config_lock:
                config_ = await self.guild_config_collection.find_one(
                    {"guild_id": {"$eq": lookup}}
                )

                if not config_:
                    await self.logger.debug("No config found in MongoDB")
                    if create_if_none:
                        config_ = await self.create_new_context_config(lookup)
                else:
                    config_ = await self.sync_config(config_)

                if config_:
                    self.guild_config_cache[lookup] = config_

        time_taken = (time.time() - start) * 1000.0

        if time_taken > self.CONFIG_RECEIVE_WARNING_TIME_MS:
            await self.logger.warning(
                f"Context config receive time = {time_taken} ms (over {self.CONFIG_RECEIVE_WARNING_TIME_MS} threshold)",
                send=True,
            )

        await self.logger.debug(
            f"Getting config for lookup key: {lookup} (time taken = {time_taken} ms)"
        )

        return config_

    async def create_new_context_config(self, lookup):
        """Creates a new guild config based on a lookup key (usually a guild ID).

        parameters:
            lookup (str): the primary key for the guild config document object
        """
        extensions_config = munch.Munch()

        await self.logger.debug("Evaluating extension data")
        for extension_name, extension_config in self.extension_configs.items():
            if extension_config:
                # don't attach to guild config if extension isn't configurable
                extensions_config[extension_name] = extension_config.data

        config_ = munch.Munch()

        config_.guild_id = str(lookup)
        config_.command_prefix = self.file_config.main.default_prefix
        config_.logging_channel = None
        config_.member_events_channel = None
        config_.guild_events_channel = None
        config_.private_channels = []
        config_.enabled_extensions = []

        config_.extensions = extensions_config

        try:
            await self.logger.debug(f"Inserting new config for lookup key: {lookup}")
            await self.guild_config_collection.insert_one(config_)
        except Exception as exception:
            # safely finish because the new config is still useful
            await self.logger.error(
                "Could not insert guild config into MongoDB", exception=exception
            )

        return config_

    async def sync_config(self, config_object):
        """Syncs the given config with the currently loaded extensions.

        parameters:
            config_object (dict): the guild config object
        """
        config_object = munch.munchify(config_object)

        should_update = False

        await self.logger.debug("Evaluating extension data")
        for (
            extension_name,
            extension_config_from_data,
        ) in self.extension_configs.items():
            extension_config = config_object.extensions.get(extension_name)
            if not extension_config and extension_config_from_data:
                should_update = True
                await self.logger.debug(
                    f"Found extension {extension_name} not in config with ID {config_object.guild_id}"
                )
                config_object.extensions[
                    extension_name
                ] = extension_config_from_data.data

        if should_update:
            await self.logger.debug(
                f"Updating guild config for lookup key: {config_object.guild_id}"
            )
            await self.guild_config_collection.replace_one(
                {"_id": config_object.get("_id")}, config_object
            )

        return config_object
