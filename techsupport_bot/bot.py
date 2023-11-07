"""The main bot functions.
"""
import asyncio
import threading

import botlogging
import cogs as builtin_cogs
import ircrelay
import munch
from base import advanced, databases, moderation
from botlogging import LogContext, LogLevel


class TechSupportBot(advanced.AdvancedBot):
    """The main bot object."""

    def __init__(self, *args, **kwargs):
        self._startup_time = None
        self.builtin_cogs = []

        super().__init__(*args, **kwargs)

    async def start(self, *args, **kwargs):
        """Starts the event loop and blocks until interrupted."""

        if isinstance(self.logger, botlogging.DelayedLogger):
            self.logger.register_queue()
            asyncio.create_task(self.logger.run())

        # Start the IRC bot in an asynchronous task
        irc_config = getattr(self.file_config.api, "irc")
        if irc_config.enable_irc:
            await self.logger.send_log(
                message="Connecting to IRC...", level=LogLevel.DEBUG, console_only=True
            )
            # Make the IRC class in such a way to allow reload without desctruction
            # We need to pass it the running loop so it can interact with discord
            await self.start_irc()

        # this is required for the bot
        await self.logger.send_log(
            message="Connecting to MongoDB...", level=LogLevel.DEBUG, console_only=True
        )
        self.mongo = self.get_mongo_ref()

        if not self.GUILD_CONFIG_COLLECTION in await self.mongo.list_collection_names():
            await self.logger.send_log(
                message="Creating new MongoDB guild config collection...",
                level=LogLevel.DEBUG,
                console_only=True,
            )
            await self.mongo.create_collection(self.GUILD_CONFIG_COLLECTION)

        self.guild_config_collection = self.mongo[self.GUILD_CONFIG_COLLECTION]

        await self.logger.send_log(
            message="Connecting to Postgres...", level=LogLevel.DEBUG, console_only=True
        )
        try:
            self.db = await self.get_postgres_ref()
        except Exception as exception:
            await self.logger.send_log(
                message=f"Could not connect to Postgres: {exception}",
                level=LogLevel.WARNING,
                exception=exception,
                console_only=True,
            )

        await self.logger.send_log(
            message="Logging into Discord...", level=LogLevel.DEBUG, console_only=True
        )
        await super().start(self.file_config.bot_config.auth_token, *args, **kwargs)

    async def setup_hook(self):
        """This function is automatically called after the bot has been logged into discord
        This loads postgres, extensions, and the help menu
        """
        await self.logger.send_log(
            message="Loading extensions...", level=LogLevel.DEBUG, console_only=True
        )
        self.extension_name_list = []
        await self.load_extensions()

        if self.db:
            await self.logger.send_log(
                message="Syncing Postgres tables...",
                level=LogLevel.DEBUG,
                console_only=True,
            )
            self.models = munch.DefaultMunch(None)
            databases.setup_models(self)
            await self.db.gino.create_all()

        await self.logger.send_log(
            message="Loading Help commands...", level=LogLevel.DEBUG, console_only=True
        )
        self.remove_command("help")
        help_cog = builtin_cogs.Helper(self)
        await self.add_cog(help_cog)

        # Setup moderation functions
        self.moderation = moderation.ModerationFunctions(self)

        # Manually load built in cogs
        await self.load_builtin_cog(builtin_cogs.AdminControl)
        await self.load_builtin_cog(builtin_cogs.ConfigControl)
        await self.load_builtin_cog(builtin_cogs.Listener)

        # This is the guild events logging cog
        await self.load_builtin_cog(botlogging.EventLogger)

    async def start_irc(self):
        """Starts the IRC connection in a seperate thread

        Args:
            irc (irc.IRC): The IRC object to start the socket on

        Returns:
            bool: True if the connection was successful, False if it was not
        """
        irc_config = getattr(self.file_config.api, "irc")
        loop = asyncio.get_running_loop()

        irc_bot = ircrelay.IRCBot(
            loop=loop,
            server=irc_config.server,
            port=irc_config.port,
            channels=irc_config.channels,
            username=irc_config.name,
            password=irc_config.password,
        )
        self.irc = irc_bot

        irc_thread = threading.Thread(target=irc_bot.start)
        await self.logger.send_log(
            message="Logging in to IRC", level=LogLevel.INFO, console_only=True
        )
        irc_thread.start()

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
            await self.logger.send_log(
                message=f"Could not load builtin cog {cog.__name__}: {exception}",
                level=LogLevel.WARNING,
                exception=exception,
                console_only=True,
            )

    async def cleanup(self):
        """Cleans up after the event loop is interupted."""
        await self.logger.send_log(
            message="Cleaning up...", level=LogLevel.DEBUG, console_only=True
        )
        await super().close()

    async def on_guild_join(self, guild):
        """Configures a new guild upon joining.

        parameters:
            guild (discord.Guild): the guild that was joined
        """
        for cog in self.cogs.values():
            if getattr(cog, "COG_TYPE", "").lower() == "loop":
                try:
                    await cog.register_new_tasks(guild)
                except Exception as exception:
                    await self.logger.send_log(
                        message="Could not register loop tasks for cog on guild join",
                        level=LogLevel.ERROR,
                        context=LogContext(guild=guild),
                        exception=exception,
                    )

        await super().on_guild_join(guild)
