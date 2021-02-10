"""Base cogs for making plugins.
"""

import ast
import asyncio
import datetime
import inspect
import random
import re

import aiocron
import discord
import munch
from discord.ext import commands


class BaseCog(commands.Cog):
    """The base plugin.

    Complex helper methods are also based here.

    parameters:
        bot (Bot): the bot object
    """

    HAS_CONFIG = True
    ADMIN_ONLY = False
    KEEP_COG_ON_FAILURE = False
    KEEP_PLUGIN_ON_FAILURE = False
    KEEP_PLUGIN_ON_UNLOAD = False

    def __init__(self, bot, models=None):
        self.bot = bot

        # this is sure to throw a bug at some point
        self.extension_name = inspect.getmodule(self).__name__.split(".")[-1]

        self.config = self.bot.config.plugins.get(self.extension_name)
        if not self.config and self.HAS_CONFIG:
            raise ValueError(
                f"No valid configuration found for plugin {self.extension_name}"
            )

        if models is None:
            models = []
        self.models = munch.Munch()
        for model in models:
            self.models[model.__name__] = model

        self.logger = self.bot.get_logger(self.__class__.__name__)

        self.bot.loop.create_task(self._preconfig())

    def cog_unload(self):
        """Allows the state to exit after unloading."""
        if not self.KEEP_PLUGIN_ON_UNLOAD:
            self.bot.plugin_api.unload_plugin(self.extension_name)

    async def _handle_preconfig(self, handler):
        """Wrapper for performing preconfig on a plugin.

        This makes the plugin unload when there is an error.

        parameters:
            handler (asyncio.coroutine): the preconfig handler
        """
        await self.bot.wait_until_ready()
        try:
            await handler()
        except Exception as e:
            await self.logger.error(
                f"Cog preconfig error: {handler.__name__}!", exception=e
            )
            if not self.KEEP_COG_ON_FAILURE:
                self.bot.remove_cog(self)
            if not self.KEEP_PLUGIN_ON_FAILURE:
                self.bot.plugin_api.unload_plugin(self.extension_name)

    async def _preconfig(self):
        """Blocks the preconfig until the bot is ready."""
        await self._handle_preconfig(self.preconfig)

    async def preconfig(self):
        """Preconfigures the environment before starting the plugin."""

    # Heavy-lifting helpers

    async def tagged_response(self, ctx, content=None, embed=None, target=None):
        """Sends a context response with the original author tagged.

        parameters:
            ctx (Context): the context object
            message (str): the message to send
            embed (discord.Embed): the discord embed object to send
            target (discord.Member): the Discord user to tag
        """
        who_to_tag = target.mention if target else ctx.message.author.mention
        content = f"{who_to_tag} {content}" if content else who_to_tag

        message = await ctx.send(content, embed=embed)
        return message

    def get_guild_from_channel_id(self, channel_id):
        """Helper for getting the guild associated with a channel.

        parameters:
            bot (BasementBot): the bot object
            channel_id (Union[string, int]): the unique ID of the channel
        """
        for guild in self.bot.guilds:
            for channel in guild.channels:
                if channel.id == int(channel_id):
                    return guild
        return None

    def sub_mentions_for_usernames(self, content):
        """Subs a string of Discord mentions with the corresponding usernames.

        parameters:
            bot (BasementBot): the bot object
            content (str): the content to parse
        """

        def get_nick_from_id_match(match):
            id_ = int(match.group(1))
            user = self.bot.get_user(id_)
            return f"@{user.name}" if user else "@user"

        return re.sub(r"<@?!?(\d+)>", get_nick_from_id_match, content)

    async def get_json_from_attachment(
        self, ctx, message, send_msg_on_none=True, send_msg_on_failure=True
    ):
        """Returns a JSON object parsed from a message's attachment.

        parameters:
            message (Message): the message object
            send_msg_on_none (bool): True if a message should be DM'd when no attachments are found
            send_msg_on_failure (bool): True if a message should be DM'd when JSON is invalid
        """
        if not message.attachments:
            if send_msg_on_none:
                await ctx.author.send("I couldn't find any message attachments!")
            return None

        try:
            json_bytes = await message.attachments[0].read()
            json_str = json_bytes.decode("UTF-8")
            # hehehe munch ~~O< oooo
            return munch.munchify(ast.literal_eval(json_str))
        # this could probably be more specific
        except Exception as e:
            if send_msg_on_failure:
                await ctx.author.send(f"I was unable to parse your JSON: `{e}`")
            return {}

    # pylint: disable=too-many-branches, too-many-arguments
    async def paginate(self, ctx, embeds, timeout=300, tag_user=False, restrict=False):
        """Paginates a set of embed objects for users to sort through

        parameters:
            ctx (Context): the context object for the message
            embeds (Union[discord.Embed, str][]): the embeds (or URLs to render them) to paginate
            timeout (int) (seconds): the time to wait before exiting the reaction listener
            tag_user (bool): True if the context user should be mentioned in the response
            restrict (bool): True if only the caller and admins can navigate the pages
        """
        # limit large outputs
        embeds = embeds[:10]

        for index, embed in enumerate(embeds):
            if isinstance(embed, self.bot.embed_api.Embed):
                embed.set_footer(text=f"Page {index+1} of {len(embeds)}")

        index = 0
        get_args = lambda index: {
            "content": embeds[index]
            if not isinstance(embeds[index], self.bot.embed_api.Embed)
            else None,
            "embed": embeds[index]
            if isinstance(embeds[index], self.bot.embed_api.Embed)
            else None,
        }

        if tag_user:
            message = await self.tagged_response(ctx, **get_args(index))
        else:
            message = await ctx.send(**get_args(index))

        if isinstance(ctx.channel, discord.DMChannel):
            return

        start_time = datetime.datetime.now()

        for unicode_reaction in ["\u25C0", "\u25B6", "\u26D4", "\U0001F5D1"]:
            await message.add_reaction(unicode_reaction)

        while True:
            if (datetime.datetime.now() - start_time).seconds > timeout:
                break

            try:
                reaction, user = await ctx.bot.wait_for(
                    "reaction_add", timeout=timeout, check=lambda r, u: not bool(u.bot)
                )
            # this seems to raise an odd timeout error, for now just catch-all
            except Exception:
                break

            # check if the reaction should be processed
            if (reaction.message.id != message.id) or (
                restrict and user.id != ctx.author.id
            ):
                # this is checked first so it can pass to the deletion
                pass

            # move forward
            elif str(reaction) == "\u25B6" and index < len(embeds) - 1:
                index += 1
                await message.edit(**get_args(index))

            # move backward
            elif str(reaction) == "\u25C0" and index > 0:
                index -= 1
                await message.edit(**get_args(index))

            # stop pagination
            elif str(reaction) == "\u26D4" and user.id == ctx.author.id:
                break

            # delete embed
            elif str(reaction) == "\U0001F5D1" and user.id == ctx.author.id:
                await message.delete()
                break

            try:
                await reaction.remove(user)
            except discord.Forbidden:
                pass

        try:
            await message.clear_reactions()
        except (discord.Forbidden, discord.NotFound):
            pass

    def task_paginate(self, *args, **kwargs):
        """Creates a pagination task.

        This is useful if you want your command to finish executing when pagination starts.

        parameters:
            ctx (Context): the context object for the message
            *args (...list): the args with which to call the pagination method
            **kwargs (...dict): the keyword args with which to call the pagination method
        """
        self.bot.loop.create_task(self.paginate(*args, **kwargs))


class MatchCog(BaseCog):
    """
    Plugin for matching a specific context criteria and responding.

    This makes the process of handling events simpler for development.
    """

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listens for a message and passes it to the response handler if valid.

        parameters:
            message (message): the message object
        """
        if message.author == self.bot.user:
            return

        ctx = await self.bot.get_context(message)

        result = await self.match(ctx, message.content)
        if not result:
            return

        await self.response(ctx, message.content)

    async def match(self, _ctx, _content):
        """Runs a boolean check on message content.

        parameters:
            ctx (context): the context object
            content (str): the message content
        """
        return True

    async def response(self, ctx, content):
        """Performs a response if the match is valid.

        parameters:
            ctx (context): the context object
            content (str): the message content
        """


class LoopCog(BaseCog):
    """Plugin for various types of looping including cron-config.

    This currently doesn't utilize the tasks library.

    parameters:
        bot (Bot): the bot object
    """

    DEFAULT_WAIT = 30
    WAIT_KEY = None
    UNITS = "seconds"
    CONVERSIONS = {"seconds": 1, "minutes": 60, "hours": 3600}
    UNLOAD_AFTER_LOOP = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conversion_factor = self.CONVERSIONS.get(self.UNITS, 1)
        self.state = True
        self.bot.loop.create_task(self._loop_execute())
        self.execution_locked = False

    async def _loop_execute(self):
        """Loops through the execution method."""
        await self._loop_preconfig()

        if not self.config.get("on_start"):
            await self.wait()

        while self.state:
            if not self.execution_locked:
                await self.bot.loop.create_task(
                    self._execute()
                )  # pylint: disable=not-callable
                await self.wait()
            else:
                await asyncio.sleep(1)

        if self.UNLOAD_AFTER_LOOP:
            self.bot.plugin_api.unload_plugin(self.extension_name)

    async def _execute(self):
        """Private method for performing the main execution method."""
        self.execution_locked = True

        try:
            await self.execute()
        except Exception as e:
            # exceptions here aren't caught by the bot's on_error,
            # so catch them manually
            await self.logger.error(
                f"Loop cog error: {self.__class__.__name__}!", exception=e
            )

        self.execution_locked = False

    def cog_unload(self):
        """Allows the loop to exit after unloading."""
        self.state = False
        super().cog_unload()

    # pylint: disable=method-hidden
    async def wait(self):
        """The default wait method."""
        if self.config.get("cron_config"):
            await aiocron.crontab(self.config.cron_config).next()
        else:
            if self.config.get(self.WAIT_KEY):
                sleep_time = self.config.get(self.WAIT_KEY) * self.conversion_factor
            else:
                sleep_time = self.DEFAULT_WAIT

            await asyncio.sleep(sleep_time)

    def setup_random_waiting(self, min_key, max_key):
        """Validates min and max wait times from config and sets the wait method to be random.

        parameters:
            min_key (str): the key to lookup the min wait config value
            max_key (str): the key to lookup the max wait config value
            units (str): the units that the wait times are in
        """
        min_wait = self.config.get(min_key)
        max_wait = self.config.get(max_key)

        if not min_wait or not max_wait:
            raise RuntimeError(
                f"Min and/or max wait times not found from keys {min_key}, {max_key}"
            )
        if min_wait < 0 or max_wait < 0:
            raise RuntimeError("Min and max times must both be greater than 0")
        if max_wait - min_wait <= 0:
            raise RuntimeError("Max time must be greater than min time")

        # pylint: disable=method-hidden
        async def random_wait():
            await asyncio.sleep(
                random.randint(
                    min_wait * self.conversion_factor, max_wait * self.conversion_factor
                )
            )

        self.wait = random_wait

    async def _loop_preconfig(self):
        """Blocks the loop_preconfig until the bot is ready."""
        await self._handle_preconfig(self.loop_preconfig)

    async def loop_preconfig(self):
        """Preconfigures the environment before starting the loop."""

    async def execute(self):
        """Runs sequentially after each wait method."""
        raise RuntimeError("Execute function must be defined in sub-class")
