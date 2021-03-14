"""Base cogs for making plugins.
"""

import ast
import asyncio
import datetime
import inspect
import re

import discord
import munch
from discord.ext import commands


class BaseCog(commands.Cog):
    """The base plugin.

    Complex helper methods are also based here.

    parameters:
        bot (Bot): the bot object
    """

    ADMIN_ONLY = False
    KEEP_COG_ON_FAILURE = False
    KEEP_PLUGIN_ON_FAILURE = False
    KEEP_PLUGIN_ON_UNLOAD = False

    def __init__(self, bot, models=None):
        self.bot = bot

        # this is sure to throw a bug at some point
        self.extension_name = inspect.getmodule(self).__name__.split(".")[-1]

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

        config = await self.bot.get_context_config(ctx)
        if not config:
            return

        result = await self.match(config, ctx, message.content)
        if not result:
            return

        await self.response(config, ctx, message.content)

    async def match(self, _config, _ctx, _content):
        """Runs a boolean check on message content.

        parameters:
            config (dict): the config associated with the context
            ctx (context): the context object
            content (str): the message content
        """
        return True

    async def response(self, _config, _ctx, _content):
        """Performs a response if the match is valid.

        parameters:
            config (dict): the config associated with the context
            ctx (context): the context object
            content (str): the message content
        """


class LoopCog(BaseCog):
    """Plugin for various types of looping including cron-config.

    This currently doesn't utilize the tasks library.

    parameters:
        bot (Bot): the bot object
    """

    DEFAULT_WAIT = 300
    ON_START = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = True
        self.bot.loop.create_task(self._loop_preconfig())

    async def _loop_preconfig(self):
        """Blocks the loop_preconfig until the bot is ready."""
        await self._handle_preconfig(self.loop_preconfig)

        for guild in self.bot.guilds:
            self.bot.loop.create_task(self._loop_execute(guild))

    async def loop_preconfig(self):
        """Preconfigures the environment before starting the loop."""

    async def _loop_execute(self, guild):
        """Loops through the execution method.

        parameters:
            guild (discord.Guild): the guild associated with the execution
        """
        config = await self.bot.get_context_config(ctx=None, guild=guild)

        if not self.ON_START:
            await self.wait(config, guild)

        while self.state:
            # refresh the config on every loop step
            config = await self.bot.get_context_config(ctx=None, guild=guild)

            try:
                await self.execute(config, guild)
            except Exception as e:
                # always try to wait even when execute fails
                await self.logger.error(
                    f"Loop cog execute error: {self.__class__.__name__}!", exception=e
                )

            try:
                await self.wait(config, guild)
            except Exception as e:
                await self.logger.error(
                    f"Loop wait cog error: {self.__class__.__name__}!", exception=e
                )
                # avoid spamming
                await self._default_wait()

    async def execute(self, _config, _guild):
        """Runs sequentially after each wait method.

        parameters:
            config (munch.Munch): the config object for the guild
            guild (discord.Guild): the guild associated with the execution
        """

    async def _default_wait(self):
        await asyncio.sleep(self.DEFAULT_WAIT)

    async def wait(self, _config, _guild):
        """The default wait method.

        parameters:
            config (munch.Munch): the config object for the guild
            guild (discord.Guild): the guild associated with the execution
        """
        await self._default_wait()

    def cog_unload(self):
        """Allows the loop to exit after unloading."""
        self.state = False
        super().cog_unload()
