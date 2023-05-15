"""Module for defining the extensions bot methods."""

import asyncio
import glob
import os

import botlogging
import discord
import munch
import yaml
from discord.ext import commands


class ExtensionConfig:
    """Represents the config of an extension."""

    # pylint: disable=too-few-public-methods
    def __init__(self):
        self.data = munch.DefaultMunch(None)

    # pylint: disable=too-many-arguments
    def add(self, key, datatype, title, description, default):
        """Adds a new entry to the config.

        This is usually used in the extensions's setup function.

        parameters:
            key (str): the lookup key for the entry
            datatype (str): the datatype metadata for the entry
            title (str): the title of the entry
            description (str): the description of the entry
            default (Any): the default value to use for the entry
        """
        self.data[key] = {
            "datatype": datatype,
            "title": title,
            "description": description,
            "default": default,
            "value": default,
        }


class ExtensionsBot(commands.Bot):
    """Parent bot object that supports extensions and basic file config."""

    CONFIG_PATH = "./config.yml"
    EXTENSIONS_DIR_NAME = "extensions"
    EXTENSIONS_DIR = (
        f"{os.path.join(os.path.dirname(__file__))}/../{EXTENSIONS_DIR_NAME}"
    )
    ExtensionConfig = ExtensionConfig

    def __init__(self, prefix=".", intents=None, allowed_mentions=None):
        self.extension_configs = munch.DefaultMunch(None)
        self.extension_states = munch.DefaultMunch(None)
        self.file_config = None
        self.load_file_config()

        super().__init__(
            command_prefix=prefix, intents=intents, allowed_mentions=allowed_mentions
        )

        if self.file_config.main.logging.queue_enabled:
            self.logger = botlogging.DelayedLogger(
                bot=self,
                name=self.__class__.__name__,
                send=not self.file_config.main.logging.block_discord_send,
                wait_time=self.file_config.main.logging.queue_wait_seconds,
            )

        else:
            self.logger = botlogging.BotLogger(
                bot=self,
                name=self.__class__.__name__,
                send=not self.file_config.main.logging.block_discord_send,
            )

    def run(self, *args, **kwargs):
        """Runs the bot, but uses the file config auth token instead of args."""
        super().run(self.file_config.main.auth_token, *args, **kwargs)

    def load_file_config(self, validate=True):
        """Loads the config yaml file into a bot object.

        parameters:
            validate (bool): True if validations should be ran on the file
        """
        with open(self.CONFIG_PATH, encoding="utf8") as iostream:
            config_ = yaml.safe_load(iostream)

        self.file_config = munch.munchify(config_)

        self.file_config.main.disabled_extensions = (
            self.file_config.main.disabled_extensions or []
        )

        if not validate:
            return

        for subsection in ["required"]:
            self.validate_bot_config_subsection("main", subsection)

    def validate_bot_config_subsection(self, section, subsection):
        """Loops through a config subsection to check for missing values.

        parameters:
            section (str): the section name containing the subsection
            subsection (str): the subsection name
        """
        for key, value in self.file_config.get(section, {}).get(subsection, {}).items():
            error_key = None
            if value is None:
                error_key = key
            elif isinstance(value, dict):
                for k, v in value.items():
                    if v is None:
                        error_key = k
            if error_key:
                raise ValueError(
                    f"Config key {error_key} from {section}.{subsection} not supplied"
                )

    async def get_potential_extensions(self):
        """Gets the current list of extensions in the defined directory."""
        self.logger.console.info(f"Searching {self.EXTENSIONS_DIR} for extensions")
        return [
            os.path.basename(f)[:-3]
            for f in glob.glob(f"{self.EXTENSIONS_DIR}/*.py")
            if os.path.isfile(f) and not f.endswith("__init__.py")
        ]

    async def load_extensions(self, graceful=True):
        """Loads all extensions currently in the extensions directory.

        parameters:
            graceful (bool): True if extensions should gracefully fail to load
        """
        self.logger.console.debug("Retrieving extensions")
        for extension_name in await self.get_potential_extensions():
            if extension_name in self.file_config.main.disabled_extensions:
                self.logger.console.debug(
                    f"{extension_name} is disabled on startup - ignoring load"
                )
                continue

            try:
                await self.load_extension(
                    f"{self.EXTENSIONS_DIR_NAME}.{extension_name}"
                )
            except Exception as exception:
                self.logger.console.error(
                    f"Failed to load extension {extension_name}: {exception}"
                )
                if not graceful:
                    raise exception

    def add_extension_config(self, extension_name, config):
        """Adds a base config object for a given extension.

        parameters:
            extension_name (str): the name of the extension
            config (ExtensionConfig): the extension config object
        """
        if not isinstance(config, self.ExtensionConfig):
            raise ValueError("config must be of type ExtensionConfig")
        self.extension_configs[extension_name] = config

    def get_command_extension_name(self, command):
        """Gets the subname of an extension from a command.

        parameters:
            command (discord.ext.commands.Command): the command to reference
        """
        if not command.module.startswith(f"{self.EXTENSIONS_DIR_NAME}."):
            return None
        extension_name = command.module.split(".")[1]
        return extension_name

    async def register_file_extension(self, extension_name, fp):
        """Offers an interface for loading an extension from an external source.

        This saves the external file data to the OS, without any validation.

        parameters:
            extension_name (str): the name of the extension to register
            fp (io.BufferedIOBase): the file-like object to save to disk
        """
        if not extension_name:
            raise NameError("Invalid extension name")

        try:
            await self.unload_extension(f"{self.EXTENSIONS_DIR_NAME}.{extension_name}")
        except commands.errors.ExtensionNotLoaded:
            pass

        with open(f"{self.EXTENSIONS_DIR}/{extension_name}.py", "wb") as file_handle:
            file_handle.write(fp)


async def extension_help(self, ctx, extension_name):
    """Automatically prompts for help if improper syntax for an extension is called.

    The format for extension_name that's used is `self.__module__[11:]`, because
    all extensions have the value set to extension.<name>, it's the most reliable
    way to get the extension name regardless of aliases

    parameters:
        ctx (discord.ext.Context): context of the message
        extension_name (str): the name of the extension to show the help for
    """

    def get_help_embed_for_extension(self, extension_name, command_prefix):
        """Gets the help embed for an extension.

        Defined so it doesn't have to be written out twice

        parameters:
            extension_name (str): the name of the extension to show the help for
            command_prefix (str): passed to the func as it has to be awaited

        returns:
            embed (discord.Embed): Embed containing all commands with their description
        """
        embed = discord.Embed()
        embed.title = f"Extension Commands: `{extension_name}`"

        # Loops through each command in the bots library
        for command in self.bot.walk_commands():
            # Gets the command name
            command_extension_name = self.bot.get_command_extension_name(command)

            # Continues the loop if the command isn't a part of the target extension
            if extension_name != command_extension_name or issubclass(
                command.__class__, commands.Group
            ):
                continue

            if command.full_parent_name == "":
                syntax = f"{command_prefix}{command.name}"

            else:
                syntax = f"{command_prefix}{command.full_parent_name} {command.name}"

            usage = command.usage or ""

            embed.add_field(
                name=f"`{syntax} {usage}`",
                value=command.description or "No description available",
                inline=False,
            )

        # Default for when no matching commands were found
        if len(embed.fields) == 0:
            embed.description = "There are no commands for this extension"

        return embed

    # Checks whether the first given argument is valid if more than one argument is supplied
    if len(ctx.message.content.split()) > 1 and ctx.message.content.split().pop(
        1
    ) not in [
        command.name
        for command in self.bot.get_cog(self.qualified_name).walk_commands()
    ]:
        if await ctx.confirm(
            "Invalid argument! Show help command?", delete_after=True, timeout=10
        ):
            await ctx.send(
                embed=get_help_embed_for_extension(
                    self, extension_name, await self.bot.get_prefix(ctx.message)
                )
            )

    # Checks if no arguments were supplied
    elif len(ctx.message.content.split()) < 2:
        await ctx.send(
            embed=get_help_embed_for_extension(
                self, extension_name, await self.bot.get_prefix(ctx.message)
            )
        )
