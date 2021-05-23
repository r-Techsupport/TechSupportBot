"""Module for admin commands.
"""

import json
import sys

import base
import decorate
import discord
from discord.ext import commands, ipc


class AdminControl(base.BaseCog):
    """Cog object for admin-only bot control"""

    ADMIN_ONLY = True

    GITHUB_API_BASE_URL = "https://api.github.com"

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
            await self.bot.send_with_mention(ctx, f"Error: {error}")
            return

        if plugin_name:
            status = status_data.get(plugin_name)
            if not status:
                await self.bot.send_with_mention(ctx, "Plugin not found!")
                return

            await self.bot.send_with_mention(ctx, f"Plugin is {status}")
            return

        embeds = []
        field_counter = 1
        for index, key in enumerate(list(status_data.keys())):
            embed = (
                discord.Embed(title="Plugin Status") if field_counter == 1 else embed
            )
            embed.add_field(name=key, value=status_data[key], inline=False)
            if field_counter == 5 or index == len(status_data) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        self.bot.task_paginate(ctx, embeds)

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
        await self.bot.send_with_mention(ctx, response.message)

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
        await self.bot.send_with_mention(ctx, response.message)

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
            await self.bot.send_with_mention(ctx, f"No such command: `{command_name}`")
            return

        if command_.enabled:
            await self.bot.send_with_mention(
                ctx, f"Command `{command_name}` is already enabled!"
            )
            return

        command_.enabled = True
        await self.bot.send_with_mention(
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
            await self.bot.send_with_mention(ctx, f"No such command: `{command_name}`")
            return

        if not command_.enabled:
            await self.bot.send_with_mention(
                ctx, f"Command `{command_name}` is already disabled!"
            )
            return

        command_.enabled = False
        await self.bot.send_with_mention(
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
        await self.bot.send_with_mention(
            ctx, f"Successfully set game to: *{game_name}*"
        )

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
        await self.bot.send_with_mention(ctx, f"Successfully set nick to: *{nick}*")

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
            await self.bot.send_with_mention(ctx, "I couldn't find that channel")
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
            await self.bot.send_with_mention(ctx, "I couldn't find that user")
            return

        await user.send(content=message)

    @commands.command(name="restart")
    async def restart(self, ctx):
        """Restarts the bot.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
        """
        await self.bot.send_with_mention(ctx, "Shutting down! Cya later!")
        sys.exit()

    @commands.command(name="leave")
    async def leave(self, ctx, *, guild_id: int):
        """Leaves a guild by ID.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
            guild_id (int): the ID of the guild to leave
        """
        guild = discord.utils.get(self.bot.guilds, id=guild_id)
        if not guild:
            await self.bot.send_with_mention(ctx, "I don't appear to be in that guild")
            return

        await guild.leave()

        await ctx.send(f"I have left the guild: {guild.name} ({guild.id})")

    @commands.command(name="bot")
    async def _bot_data(self, ctx):
        """Gets various data about the bot.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
        """
        embed = discord.Embed(title=self.bot.user.name)

        embed.add_field(
            name="Started",
            value=f"{self.bot.startup_time} UTC" if self.bot.startup_time else "None",
            inline=False,
        )
        embed.add_field(
            name="Latency",
            value=f"{self.bot.latency*1000} ms" if self.bot.latency else "None",
            inline=False,
        )
        embed.add_field(
            name="Description", value=self.bot.description or "None", inline=False
        )
        embed.add_field(
            name="Servers",
            value=", ".join(f"{guild.name} ({guild.id})" for guild in self.bot.guilds),
            inline=False,
        )

        embed.set_thumbnail(url=self.bot.user.avatar_url)

        await self.bot.send_with_mention(ctx, embed=embed)

    @decorate.with_typing
    @commands.command(name="issue", aliases=["ish", "botish", "botissue"])
    async def issue(self, ctx, title: str, description: str):
        """Creates an issue in the bot's Github Repo

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
            title: the title of the issue
            description: the description of the issue
        """

        icon_url = (
            "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
        )

        oauth_token = self.bot.config.main.api_keys.github
        if not oauth_token:
            await self.bot.send_with_mention(ctx, "I couldn't authenticate with Github")
            return

        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "text/plain",
        }

        data = {"title": title, "body": description}

        username = self.bot.config.special.github.username
        repo = self.bot.config.special.github.repo
        if not username or not repo:
            await self.bot.send_with_mention(ctx, "I couldn't find the repository")
            return

        response = await self.bot.http_call(
            "post",
            f"{self.GITHUB_API_BASE_URL}/repos/{username}/{repo}/issues",
            headers=headers,
            data=json.dumps(data),
        )

        status_code = response.get("status_code")
        if status_code != 201:
            await self.bot.send_with_mention(
                ctx, f"I was unable to create your issue (status code {status_code})"
            )
            return

        issue_url = response.get("html_url")
        number = response.get("number")

        embed = discord.Embed(title="Issue Created")
        embed.add_field(name=f"Issue #{number}", value=f"{issue_url}")
        embed.set_thumbnail(url=icon_url)

        await self.bot.send_with_mention(ctx, embed=embed)

    @ipc.server.route(name="health")
    async def health_endpoint(self, _):
        """Returns a 200 code in the best of circumstances."""
        return self.bot.ipc_response()

    @ipc.server.route(name="describe")
    async def describe_endpoint(self, _):
        """Gets all relevant bot information."""
        return self.bot.ipc_response(payload=self.bot.preserialize_object(self.bot))

    @ipc.server.route(name="get_plugin_status")
    async def plugin_status_endpoint(self, _):
        """IPC endpoint for getting plugin status."""
        return self.bot.ipc_response(payload=self.bot.plugin_api.get_status())

    @ipc.server.route(name="load_plugin")
    async def load_plugin_endpoint(self, data):
        """IPC endpoint for loading a plugin.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.plugin_name:
            return self.bot.ipc_response(code=400, error="Plugin name not provided")

        response = self.bot.plugin_api.load_plugin(data.plugin_name)
        if not response.status:
            return self.bot.ipc_response(code=500, error=response.message)

        return self.bot.ipc_response()

    @ipc.server.route(name="unload_plugin")
    async def unload_plugin_endpoint(self, data):
        """IPC endpoint for unloading a plugin.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.plugin_name:
            return self.bot.ipc_response(code=400, error="Plugin name not provided")

        response = self.bot.plugin_api.unload_plugin(data.plugin_name)
        if not response.status:
            return self.bot.ipc_response(code=500, error=response.message)

        return self.bot.ipc_response()

    @ipc.server.route(name="echo_user")
    async def echo_user_endpoint(self, data):
        """IPC endpoint for DMing a user.

        parameters:
            data (object): the data provided by the client request
        """
        user = await self.bot.fetch_user(int(data.user_id))
        if not user:
            return self.bot.ipc_response(code=404, error="User not found")

        await user.send(content=data.message)

        return self.bot.ipc_response()

    @ipc.server.route(name="echo_channel")
    async def echo_channel_endpoint(self, data):
        """IPC endpoint for sending to a channel.

        parameters:
            data (object): the data provided by the client request
        """
        channel = self.bot.get_channel(int(data.channel_id))
        if not channel:
            return self.bot.ipc_response(code=404, error="Channel not found")

        await channel.send(content=data.message)

        return self.bot.ipc_response()

    @ipc.server.route(name="get_all_guilds")
    async def get_all_guilds_endpoint(self, _):
        """IPC endpoint for getting all guilds."""
        guilds = [self.bot.preserialize_object(guild) for guild in self.bot.guilds]
        return self.bot.ipc_response(payload={"guilds": guilds})

    @ipc.server.route(name="get_guild")
    async def get_guild_endpoint(self, data):
        """IPC endpoint for getting a single guild.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return self.bot.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return self.bot.ipc_response(code=404, error="Guild not found")

        return self.bot.ipc_response(payload=self.bot.preserialize_object(guild))

    @ipc.server.route(name="leave_guild")
    async def leave_guild_endpoint(self, data):
        """IPC endpoint for getting a single guild.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return self.bot.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return self.bot.ipc_response(code=404, error="Guild not found")

        await guild.leave()

        return self.bot.ipc_response()
