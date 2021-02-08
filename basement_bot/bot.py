"""The main bot functions.
"""

import sys

import admin
import database
import discord
import embed
import error
import logger
import munch
import plugin
import yaml
from discord.ext import commands

log = logger.get_logger("Basement Bot")

# pylint: disable=too-many-instance-attributes
class BasementBot(commands.Bot):
    """The main bot object.

    parameters:
        run (bool): True if the bot should run on instantiation
        validate_config (bool): True if the bot's config should be validated
    """

    CONFIG_PATH = "./config.yaml"

    def __init__(self, run=True, validate_config=True):
        # the config API will set this
        self.config = None
        self.load_config(validate=validate_config)

        self.plugin_api = plugin.PluginAPI(bot=self)
        self.database_api = database.DatabaseAPI(bot=self)
        self.error_api = error.ErrorAPI(bot=self)
        self.embed_api = embed.EmbedAPI(bot=self)

        super().__init__(self.config.main.required.command_prefix)

        if run:
            log.debug("Bot starting upon init")
            self.start(self.config.main.required.auth_token)
        else:
            log.debug("Bot created but not started")

    async def on_ready(self):
        """Callback for when the bot is finished starting up."""
        game = self.config.main.optional.get("game")
        if game:
            await self.change_presence(activity=discord.Game(name=game))

        log.info(f"Commands available with the `{self.command_prefix}` prefix")

    async def on_message(self, message):
        """Catches messages and acts appropriately.

        parameters:
            message (discord.Message): the message object
        """
        owner = await self.get_owner()

        if (
            owner
            and isinstance(message.channel, discord.DMChannel)
            and message.author.id != owner.id
            and not message.author.bot
        ):
            await owner.send(f'PM from {message.author.mention}: "{message.content}"')

        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def on_error(self, event_method, *args, **kwargs):
        """Catches non-command errors and sends them to the error API for processing.

        parameters:
            event_method (str): the event method associated with the error (eg. message)
        """
        _, exception, _ = sys.exc_info()
        await self.error_api.handle_error(event_method, exception)

    async def on_command_error(self, context, exception):
        """Catches command errors and sends them to the error API for processing.

        parameters:
            context (discord.Context): the context associated with the exception
            exception (Exception): the exception object associated with the error
        """
        await self.error_api.handle_command_error(context, exception)

    # pylint: disable=invalid-overridden-method
    def start(self, *args, **kwargs):
        """Loads initial plugins (blocking) and starts the connection."""
        log.debug("Starting bot...")

        self.plugin_api.load_plugins()

        try:
            self.add_cog(admin.AdminControl(self))
        except (TypeError, commands.CommandError) as e:
            log.warning(f"Could not load AdminControl cog: {e}")

        try:
            self.loop.run_until_complete(super().start(*args, **kwargs))
        except (SystemExit, KeyboardInterrupt):
            self.loop.run_until_complete(self.logout())
        finally:
            self.loop.close()

    async def get_owner(self):
        """Gets the owner object for the bot application."""
        try:
            app_info = await self.application_info()
            return app_info.owner
        except discord.errors.HTTPException:
            return None

    async def can_run(self, ctx, *, call_once=False):
        """Wraps the default can_run check to evaluate if a check call is necessary.

        This method wraps the GroupMixin method.

        parameters:
            ctx (discord.Context): the context associated with the command
            call_once (bool): True if the check should be retrieved from the call_once attribute
        """
        is_bot_admin = await self.is_bot_admin(ctx)

        if is_bot_admin:
            return True

        # the user is not a bot admin, so they can't do this
        cog = getattr(ctx.command, "cog", None)
        if getattr(cog, "ADMIN_ONLY", False):
            # treat this as a command error to be caught by the dispatcher
            raise commands.MissingPermissions(["bot_admin"])

        result = await super().can_run(ctx, call_once=call_once)
        return result

    async def is_bot_admin(self, ctx):
        """Processes command context against admin/owner data.

        Command checks are disabled if the context author is the owner.

        They are also ignored if the author is bot admin in the config.

        parameters:
            ctx (discord.Context): the context associated with the command
        """
        owner = await self.get_owner()
        if getattr(owner, "id", None) == ctx.author.id:
            return True

        if ctx.message.author.id in [int(id) for id in self.config.main.admins.ids]:
            return True

        role_is_admin = False
        for role in getattr(ctx.message.author, "roles", []):
            if role.name in self.config.main.admins.roles:
                role_is_admin = True
                break
        if role_is_admin:
            return True

        return False

    def load_config(self, validate):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH) as iostream:
            config = yaml.safe_load(iostream)
        self.config = munch.munchify(config)

        self.config.main.disabled_plugins = self.config.main.disabled_plugins or []

        if validate:
            self.validate_config()

    def validate_config(self):
        """Validates several config subsections."""
        for subsection in ["required", "database"]:
            self.validate_config_subsection("main", subsection)
        for subsection in list(self.config.plugins.keys()):
            self.validate_config_subsection("plugins", subsection)

    def validate_config_subsection(self, section, subsection):
        """Loops through a config subsection to check for missing values.

        parameters:
            section (str): the section name containing the subsection
            subsection (str): the subsection name
        """
        for key, value in self.config.get(section, {}).get(subsection, {}).items():
            error_key = None
            if value is None:
                error_key = key
            elif isinstance(value, dict):
                for k, v in value.items():
                    if v is None:
                        error_key = k
            if error_key:
                if section == "plugins":
                    if not subsection in self.config.main.disabled_plugins:
                        # pylint: disable=line-too-long
                        log.warning(
                            f"Disabling loading of plugin {subsection} due to missing config key {error_key}"
                        )
                        # disable the plugin if we can't get its config
                        self.config.main.disabled_plugins.append(subsection)
                else:
                    raise ValueError(
                        f"Config key {error_key} from {section}.{subsection} not supplied"
                    )

    def generate_amqp_url(self):
        """Dynamically converts config to an AMQP URL.
        """
        host = self.config.main.rabbitmq.host
        port = self.config.main.rabbitmq.port
        vhost = self.config.main.rabbitmq.vhost
        user = self.config.main.rabbitmq.user
        password = self.config.main.rabbitmq.password

        return f"amqp://{user}:{password}@{host}:{port}{vhost}"

    def get_modules(self):
        """Gets the current list of plugin modules."""
        return [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.PLUGINS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]
