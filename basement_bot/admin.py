"""Cog for controlling the bot.
"""

import sys

import cogs
import decorate
from discord.ext import commands


class AdminControl(cogs.BaseCog):
    """Cog object for admin-only bot control"""

    ADMIN_ONLY = True
    HAS_CONFIG = False

    @commands.group(
        name="plugin",
        brief="Executes a plugin bot command",
        description="Executes a plugin bot command",
    )
    async def plugin_group(self, ctx):
        # pylint: disable=missing-function-docstring
        pass

    @decorate.with_typing
    @plugin_group.command(name="status")
    async def plugin_status(self, ctx, *, plugin_name: str = None):
        """Gets the status of the bot plugins.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            plugin_name (str): the name of the plugin
        """
        status_data = ctx.bot.plugin_api.get_status()

        error = status_data.get("error")
        if error:
            await self.tagged_response(ctx, f"Error: {error}")
            return

        if plugin_name:
            status = status_data.get(plugin_name)
            if not status:
                await self.tagged_response(ctx, "Plugin not found!")
                return

            await self.tagged_response(ctx, f"Plugin is {status}")
            return

        embeds = []
        field_counter = 1
        for index, key in enumerate(list(status_data.keys())):
            embed = (
                self.bot.embed_api.Embed(title="Plugin Status")
                if field_counter == 1
                else embed
            )
            embed.add_field(name=key, value=status_data[key], inline=False)
            if field_counter == 5 or index == len(status_data) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        self.task_paginate(ctx, embeds)

    @decorate.with_typing
    @plugin_group.command(name="load")
    async def load_plugin(self, ctx, *, plugin_name: str):
        """Loads a plugin by filename.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            plugin_name (str): the name of the plugin
        """
        response = ctx.bot.plugin_api.load_plugin(plugin_name)
        await self.tagged_response(ctx, response.message)

    @decorate.with_typing
    @plugin_group.command(name="unload")
    async def unload_plugin(self, ctx, *, plugin_name: str):
        """Unloads a plugin by filename.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            plugin_name (str): the name of the plugin
        """
        response = ctx.bot.plugin_api.unload_plugin(plugin_name)
        await self.tagged_response(ctx, response.message)

    @commands.group(
        name="command",
        brief="Executes a commands bot command",
        description="Executes a commands bot command",
    )
    async def command_group(self, ctx):
        # pylint: disable=missing-function-docstring
        pass

    @decorate.with_typing
    @command_group.command(name="enable")
    async def enable_command(self, ctx, *, command_name: str):
        """Enables a command by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            command_name (str): the name of the command
        """
        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await self.tagged_response(ctx, f"No such command: `{command_name}`")
            return

        if command_.enabled:
            await self.tagged_response(
                ctx, f"Command `{command_name}` is already enabled!"
            )
            return

        command_.enabled = True
        await self.tagged_response(
            ctx, f"Successfully enabled command: `{command_name}`"
        )

    @decorate.with_typing
    @command_group.command(name="disable")
    async def disable_command(self, ctx, *, command_name: str):
        """Disables a command by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            command_name (str): the name of the command
        """
        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await self.tagged_response(ctx, f"No such command: `{command_name}`")
            return

        if not command_.enabled:
            await self.tagged_response(
                ctx, f"Command `{command_name}` is already disabled!"
            )
            return

        command_.enabled = False
        await self.tagged_response(
            ctx, f"Successfully disabled command: `{command_name}`"
        )

    @commands.group(
        name="set",
        brief="Executes a `set X` bot command",
        description="Executes a `set X` bot command",
    )
    async def set_group(self, ctx):
        # pylint: disable=missing-function-docstring
        pass

    @decorate.with_typing
    @set_group.command(name="game")
    async def set_game(self, ctx, *, game_name: str):
        """Sets the bot's game (activity) by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            game_name (str): the name of the game
        """
        await ctx.bot.set_game(game_name)
        await self.tagged_response(ctx, f"Successfully set game to: *{game_name}*")

    @decorate.with_typing
    @set_group.command(name="nick")
    async def set_nick(self, ctx, *, nick: str):
        """Sets the bot's nick by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            nick (str): the bot nickname
        """
        await ctx.message.guild.me.edit(nick=nick)
        await self.tagged_response(ctx, f"Successfully set nick to: *{nick}*")

    @commands.group(
        brief="Executes an echo bot command", description="Executes an echo bot command"
    )
    async def echo(self, ctx):
        # pylint: disable=missing-function-docstring
        pass

    @decorate.with_typing
    @echo.command(name="channel")
    async def echo_channel(self, ctx, channel_id: int, *, message: str):
        """Sends a message to a specified channel.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
            channel_id (int): the ID of the channel to send the echoed message
            message (str): the message to echo
        """
        channel = self.bot.get_channel(channel_id)
        if not channel:
            await self.tagged_response(ctx, "I couldn't find that channel")
            return

        await channel.send(content=message)

    @decorate.with_typing
    @echo.command(name="user")
    async def echo_user(self, ctx, user_id: int, *, message: str):
        """Sends a message to a specified user.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
            user_id (int): the ID of the user to send the echoed message
            message (str): the message to echo
        """
        user = await self.bot.fetch_user(int(user_id))
        if not user:
            await self.tagged_response(ctx, "I couldn't find that user")
            return

        await user.send(content=message)

    @commands.command(name="shutdown")
    async def shutdown(self, ctx):
        """Shuts down the bot.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
        """
        await self.tagged_response(ctx, "Shutting down! Cya later!")
        sys.exit()
