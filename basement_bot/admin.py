"""Cog for controlling the bot.
"""

from cogs import BasicPlugin
from discord.ext import commands
from helper import with_typing
from utils.embed import SafeEmbed


class AdminControl(BasicPlugin):
    """Cog object for admin-only bot control"""

    ADMIN_ONLY = True

    HAS_CONFIG = False
    PLUGIN_NAME = __name__

    @with_typing
    @commands.command(hidden=True)
    async def plugin_status(self, ctx, *args):
        """Gets the status of the bot plugins.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        plugin_name = args[0].lower() if args else None

        status_data = ctx.bot.plugin_api.get_status()

        error = status_data.get("error")
        if error:
            await self.bot.h.tagged_response(ctx, f"Error: {error}")
            return

        if plugin_name:
            status = status_data.get(plugin_name)
            if not status:
                await self.bot.h.tagged_response(ctx, "Plugin not found!")
                return

            await self.bot.h.tagged_response(ctx, f"Plugin is {status}")
            return

        embeds = []
        field_counter = 1
        for index, key in enumerate(list(status_data.keys())):
            embed = SafeEmbed(title="Plugin Status") if field_counter == 1 else embed
            embed.add_field(name=key, value=status_data[key], inline=False)
            if field_counter == 5 or index == len(status_data) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        self.bot.h.task_paginate(ctx, embeds)

    @with_typing
    @commands.command(hidden=True)
    async def load_plugin(self, ctx, *args):
        """Loads a plugin by filename.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        plugin_name = args[0].lower() if args else None

        if not plugin_name:
            await self.bot.h.tagged_response(ctx, "Invalid input")
            return

        response = ctx.bot.plugin_api.load_plugin(plugin_name)
        await self.bot.h.tagged_response(ctx, response.message)

    @with_typing
    @commands.command(hidden=True)
    async def unload_plugin(self, ctx, *args):
        """Unloads a plugin by filename.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        plugin_name = args[0].lower() if args else None

        if not plugin_name:
            await self.bot.h.tagged_response(ctx, "Invalid input")
            return

        response = ctx.bot.plugin_api.unload_plugin(plugin_name)
        await self.bot.h.tagged_response(ctx, response.message)

    @with_typing
    @commands.command(hidden=True)
    async def enable_command(self, ctx, *args):
        """Enables a command by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        command_name = args[0].lower() if args else None
        if not command_name:
            await self.bot.h.tagged_response(ctx, "Invalid input")
            return

        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await self.bot.h.tagged_response(ctx, f"No such command: `{command_name}`")
            return

        if command_.enabled:
            await self.bot.h.tagged_response(
                ctx, f"Command `{command_name}` is already enabled!"
            )
            return

        command_.enabled = True
        await self.bot.h.tagged_response(
            ctx, f"Successfully enabled command: `{command_name}`"
        )

    @with_typing
    @commands.command(hidden=True)
    async def disable_command(self, ctx, *args):
        """Disables a command by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        command_name = args[0].lower() if args else None
        if not command_name:
            await self.bot.h.tagged_response(ctx, "Invalid input")
            return

        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await self.bot.h.tagged_response(ctx, f"No such command: `{command_name}`")
            return

        if not command_.enabled:
            await self.bot.h.tagged_response(
                ctx, f"Command `{command_name}` is already disabled!"
            )
            return

        command_.enabled = False
        await self.bot.h.tagged_response(
            ctx, f"Successfully disabled command: `{command_name}`"
        )

    @with_typing
    @commands.command(hidden=True)
    async def set_game(self, ctx, *args):
        """Sets the bot's game (activity) by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        # TODO: put this logic in the valid_input method
        game_ = " ".join(args)[:32]

        if not self.valid_input(game_):
            await self.bot.h.tagged_response(ctx, "Invalid game!")

        await ctx.bot.set_game(game_)

        await self.bot.h.tagged_response(ctx, f"Successfully set game to: *{game_}*")

    @with_typing
    @commands.command(hidden=True)
    async def set_nick(self, ctx, *args):
        """Sets the bot's nick by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        # TODO: put this logic in the valid_input method
        nick = " ".join(args)[:32]

        if not self.valid_input(nick):
            await self.bot.h.tagged_response(ctx, "Invalid nick!")

        await ctx.message.guild.me.edit(nick=nick)

        await self.bot.h.tagged_response(ctx, f"Successfully set nick to: *{nick}*")

    @with_typing
    @commands.command(hidden=True)
    async def echo_channel(self, ctx, channel_id, *args):
        """Sends a message to a specified channel.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the calling message
            channel_id (str): the ID of the channel to send the echoed message
            args [list]: the space-or-quote-delimitted args
        """
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            await self.bot.h.tagged_response(ctx, "I couldn't find that channel")
            return

        message = " ".join(args)
        if not message:
            await self.bot.h.tagged_response(ctx, "I need a message to echo")
            return

        await channel.send(content=message)

    @with_typing
    @commands.command(hidden=True)
    async def echo_user(self, ctx, user_id, *args):
        """Sends a message to a specified user.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the calling message
            user_id (str): the ID of the user to send the echoed message
            args [list]: the space-or-quote-delimitted args
        """
        user = await self.bot.fetch_user(int(user_id))
        if not user:
            await self.bot.h.tagged_response(ctx, "I couldn't find that user")
            return

        message = " ".join(args)
        if not message:
            await self.bot.h.tagged_response(ctx, "I need a message to echo")
            return

        await user.send(content=message)

    @staticmethod
    def valid_input(input_):
        """Wrapper for validating input for bot parameters.

        parameters:
            input_ (str): the user input
        """
        return not all(char == " " for char in input_)
