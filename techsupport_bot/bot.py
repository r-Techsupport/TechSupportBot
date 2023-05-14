"""The main bot functions.
"""
import asyncio
import os

import base
import botlogging
import cogs as builtin_cogs
import context
from discord.ext import ipc


# pylint: disable=too-many-public-methods, too-many-instance-attributes
class TechSupportBot(base.AdvancedBot):
    """The main bot object."""

    IPC_SECRET_ENV_KEY = "IPC_SECRET"

    # pylint: disable=attribute-defined-outside-init
    def __init__(self, *args, **kwargs):
        self._startup_time = None
        self.ipc = None
        self.builtin_cogs = []

        super().__init__(*args, **kwargs)

    async def start(self, *args, **kwargs):
        """Starts IPC and the event loop and blocks until interrupted."""

        if isinstance(self.logger, botlogging.DelayedLogger):
            self.logger.register_queue()
            asyncio.create_task(self.logger.run())

        if os.getenv(self.IPC_SECRET_ENV_KEY):
            self.logger.console.debug("Setting up IPC server")
            self.ipc = ipc.Server(
                self, host="0.0.0.0", secret_key=os.getenv(self.IPC_SECRET_ENV_KEY)
            )
            self.ipc.start()
        else:
            self.logger.console.debug("No IPC secret found in env - ignoring IPC setup")

        # this is required for the bot
        await self.logger.debug("Connecting to MongoDB...")
        self.mongo = self.get_mongo_ref()

        if not self.GUILD_CONFIG_COLLECTION in await self.mongo.list_collection_names():
            await self.logger.debug("Creating new MongoDB guild config collection...")
            await self.mongo.create_collection(self.GUILD_CONFIG_COLLECTION)

        self.guild_config_collection = self.mongo[self.GUILD_CONFIG_COLLECTION]

        await self.logger.debug("Connecting to Postgres...")
        try:
            self.db = await self.get_postgres_ref()
        except Exception as exception:
            await self.logger.warning(f"Could not connect to Postgres: {exception}")

        await self.logger.debug("Connecting to RabbitMQ...")
        try:
            self.rabbit = await self.get_rabbit_connection()
        except Exception as exception:
            await self.logger.warning(f"Could not connect to RabbitMQ: {exception}")

        if self.db:
            await self.logger.debug("Syncing Postgres tables...")
            await self.db.gino.create_all()

        if self.ipc:
            await self.load_builtin_cog(builtin_cogs.IPCEndpoints)

        await self.logger.debug("Logging into Discord...")
        await super().start(self.file_config.main.auth_token, *args, **kwargs)

    async def setup_hook(self):
        await self.logger.debug("Loading extensions...")
        await self.load_extensions()

        await self.logger.debug("Loading Help commands...")
        self.remove_command("help")
        help_cog = builtin_cogs.Helper(self)
        await self.add_cog(help_cog)

        await self.load_builtin_cog(builtin_cogs.AdminControl)
        await self.load_builtin_cog(builtin_cogs.ConfigControl)
        await self.load_builtin_cog(builtin_cogs.Raw)
        await self.load_builtin_cog(builtin_cogs.Listener)

    async def load_builtin_cog(self, cog):
        """Loads a cog as a builtin.

        parameters:
            cog (discord.commands.ext.Cog): the cog to load
        """
        try:
            cog = cog(self)
            await self.add_cog(cog)
            self.builtin_cogs.append(cog.qualified_name)
        except Exception as exception:
            await self.logger.warning(
                f"Could not load builtin cog {cog.__name__}: {exception}"
            )

    async def cleanup(self):
        """Cleans up after the event loop is interupted."""
        await self.logger.debug("Cleaning up...", send=True)
        await super().logout()
        await self.rabbit.close()

    async def get_context(self, message, cls=context.Context):
        """Wraps the parent context creation with a custom class."""
        return await super().get_context(message, cls=cls)

    async def on_ipc_error(self, _endpoint, exception):
        """Catches IPC errors and sends them to the error logger for processing.

        parameters:
            endpoint (str): the endpoint called
            exception (Exception): the exception object associated with the error
        """
        await self.logger.error(
            f"IPC error: {exception}", exception=exception, send=True
        )

    async def on_guild_join(self, guild):
        """Configures a new guild upon joining.

        parameters:
            guild (discord.Guild): the guild that was joined
        """
        for cog in self.cogs.values():
            if getattr(cog, "COG_TYPE", "").lower() == "loop":
                try:
                    await cog.register_new_tasks(guild)
                except Exception as e:
                    await self.logger.error(
                        "Could not register loop tasks for cog on guild join",
                        exception=e,
                    )
        await super().on_guild_join(guild)
