"""Module for admin commands.
"""

import json
import re

import base
import discord
import git
import ui
import util
from base import auxiliary
from discord.ext import commands


class AdminEmbed(discord.Embed):
    """Base embed for admin commands."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.blurple()


class AdminControl(base.BaseCog):
    """Cog object for admin-only bot control"""

    ADMIN_ONLY = True

    GITHUB_API_BASE_URL = "https://api.github.com"

    @commands.group(
        name="extension",
        brief="Executes an extension bot command",
        description="Executes an extension bot command",
    )
    async def extension_group(self, ctx):
        # pylint: disable=missing-function-docstring

        # Executed if there are no/invalid args supplied
        def get_help_embed(self, command_prefix):
            # Gets commands, checks if first supplied arg is valid
            embed = discord.Embed(
                title="Incorrect/no args provided, correct command usage:"
            )

            # Loops through each command in this cog
            for command in self.bot.get_cog(self.qualified_name).walk_commands():
                if issubclass(command.__class__, commands.Group):
                    continue

                if command.full_parent_name == "":
                    syntax = f"{command_prefix}{command.name}"

                else:
                    syntax = (
                        f"{command_prefix}{command.full_parent_name} {command.name}"
                    )

                embed.color = discord.Color.green()
                embed.add_field(
                    name=f"`{syntax} {command.usage or ''}`",
                    value=command.description or "No description available",
                    inline=False,
                )

            return embed

        # Checks if no arguments were supplied
        if len(ctx.message.content.split()) < 2:
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

        # Checks whether the first given argument is valid if more than one argument is supplied
        elif ctx.message.content.split().pop(1) not in [
            command.name
            for command in self.bot.get_cog(self.qualified_name).walk_commands()
        ]:
            view = ui.Confirm()
            await view.send(
                message="Invalid argument! Show help command?",
                channel=ctx.channel,
                author=ctx.author,
                timeout=10,
            )
            await view.wait()
            if view.value != ui.ConfirmResponse.CONFIRMED:
                return
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

    @util.with_typing
    @extension_group.command(
        name="status",
        description="Gets the status of an extension by name",
        usage="[extension-name]",
    )
    async def extension_status(self, ctx, *, extension_name: str):
        """Gets the status of an extension.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_name (str): the name of the extension
        """
        status = (
            "loaded"
            if ctx.bot.extensions.get(
                f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
            )
            else "unloaded"
        )
        embed = discord.Embed(
            title=f"Extension status for `{extension_name}`", description=status
        )

        if status == "loaded":
            embed.color = discord.Color.green()
        else:
            embed.color = discord.Color.gold()

        await ctx.send(embed=embed)

    @util.with_typing
    @extension_group.command(
        name="load", description="Loads an extension by name", usage="[extension-name]"
    )
    async def load_extension(self, ctx, *, extension_name: str):
        """Loads an extension by filename.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_name (str): the name of the extension
        """
        await ctx.bot.load_extension(f"extensions.{extension_name}")
        await auxiliary.send_confirm_embed(
            message="I've loaded that extension", channel=ctx.channel
        )

    @util.with_typing
    @extension_group.command(
        name="unload",
        description="Unloads an extension by name",
        usage="[extension-name]",
    )
    async def unload_extension(self, ctx, *, extension_name: str):
        """Unloads an extension by filename.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_name (str): the name of the extension
        """
        await ctx.bot.unload_extension(f"extensions.{extension_name}")
        await auxiliary.send_confirm_embed(
            message="I've unloaded that extension", channel=ctx.channel
        )

    @util.with_typing
    @extension_group.command(
        name="register",
        description="Uploads an extension from Discord to be saved on the bot",
        usage="[extension-name] |python-file-upload|",
    )
    async def register_extension(self, ctx, extension_name: str):
        """Unloads an extension by filename.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            extension_name (str): the name of the extension
        """
        if not ctx.message.attachments:
            await auxiliary.send_deny_embed(
                message="You did not provide a Python file upload", channel=ctx.channel
            )
            return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith(".py"):
            await auxiliary.send_deny_embed(
                message="I don't recognize your upload as a Python file",
                channel=ctx.channel,
            )
            return

        if extension_name.lower() in await self.bot.get_potential_extensions():
            view = ui.Confirm()
            await view.send(
                message=f"Warning! This will replace the current `{extension_name}.py` "
                + "extension! Are you SURE?",
                channel=ctx.channel,
                author=ctx.author,
            )
            await view.wait()

            if view.value is ui.ConfirmResponse.TIMEOUT:
                return
            if view.value is ui.ConfirmResponse.DENIED:
                await auxiliary.send_deny_embed(
                    message=f"{extension_name}.py was not replaced", channel=ctx.channel
                )
                return

        fp = await attachment.read()
        await self.bot.register_file_extension(extension_name, fp)
        await auxiliary.send_confirm_embed(
            message="I've registered that extension. You can now try loading it",
            channel=ctx.channel,
        )

    @commands.group(
        name="command",
        brief="Executes a commands bot command",
        description="Executes a commands bot command",
    )
    async def command_group(self, ctx):
        # pylint: disable=missing-function-docstring

        # Executed if there are no/invalid args supplied
        def get_help_embed(self, command_prefix):
            # Gets commands, checks if first supplied arg is valid
            embed = discord.Embed(
                title="Incorrect/no args provided, correct command usage:"
            )

            # Loops through each command in this cog
            for command in self.bot.get_cog(self.qualified_name).walk_commands():
                if issubclass(command.__class__, commands.Group):
                    continue

                if command.full_parent_name == "":
                    syntax = f"{command_prefix}{command.name}"

                else:
                    syntax = (
                        f"{command_prefix}{command.full_parent_name} {command.name}"
                    )

                embed.color = discord.Color.green()
                embed.add_field(
                    name=f"`{syntax} {command.usage or ''}`",
                    value=command.description or "No description available",
                    inline=False,
                )

            return embed

        # Checks if no arguments were supplied
        if len(ctx.message.content.split()) < 2:
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

        # Checks whether the first given argument is valid if more than one argument is supplied
        elif ctx.message.content.split().pop(1) not in [
            command.name
            for command in self.bot.get_cog(self.qualified_name).walk_commands()
        ]:
            view = ui.Confirm()
            await view.send(
                message="Invalid argument! Show help command?",
                channel=ctx.channel,
                author=ctx.author,
                timeout=10,
            )
            await view.wait()
            if view.value != ui.ConfirmResponse.CONFIRMED:
                return
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

    @util.with_typing
    @command_group.command(
        name="enable", description="Enables a command by name", usage="[command-name]"
    )
    async def enable_command(self, ctx, *, command_name: str):
        """Enables a command by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            command_name (str): the name of the command
        """
        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await auxiliary.send_deny_embed(
                message=f"No such command: `{command_name}`", channel=ctx.channel
            )
            return

        if command_.enabled:
            await auxiliary.send_deny_embed(
                message=f"Command `{command_name}` is already enabled!",
                channel=ctx.channel,
            )
            return

        command_.enabled = True
        await auxiliary.send_confirm_embed(
            message=f"Successfully enabled command: `{command_name}`",
            channel=ctx.channel,
        )

    @util.with_typing
    @command_group.command(
        name="disable", description="Disables a command by name", usage="[command-name]"
    )
    async def disable_command(self, ctx, *, command_name: str):
        """Disables a command by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            command_name (str): the name of the command
        """
        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await auxiliary.send_deny_embed(
                message=f"No such command: `{command_name}`", channel=ctx.channel
            )
            return

        if not command_.enabled:
            await auxiliary.send_deny_embed(
                message=f"Command: `{command_name}` is already disabled!",
                channel=ctx.channel,
            )
            return

        command_.enabled = False
        await auxiliary.send_confirm_embed(
            message=f"Successfully disabled command: `{command_name}`",
            channel=ctx.channel,
        )

    @commands.group(
        name="set",
        brief="Executes a `set X` bot command",
        description="Executes a `set X` bot command",
    )
    async def set_group(self, ctx):
        # pylint: disable=missing-function-docstring

        # Executed if there are no/invalid args supplied
        def get_help_embed(self, command_prefix):
            # Gets commands, checks if first supplied arg is valid
            embed = discord.Embed(
                title="Incorrect/no args provided, correct command usage:"
            )

            # Loops through each command in this cog
            for command in self.bot.get_cog(self.qualified_name).walk_commands():
                if issubclass(command.__class__, commands.Group):
                    continue

                if command.full_parent_name == "":
                    syntax = f"{command_prefix}{command.name}"

                else:
                    syntax = (
                        f"{command_prefix}{command.full_parent_name} {command.name}"
                    )

                embed.color = discord.Color.green()
                embed.add_field(
                    name=f"`{syntax} {command.usage or ''}`",
                    value=command.description or "No description available",
                    inline=False,
                )

            return embed

        # Checks if no arguments were supplied
        if len(ctx.message.content.split()) < 2:
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

        # Checks whether the first given argument is valid if more than one argument is supplied
        elif ctx.message.content.split().pop(1) not in [
            command.name
            for command in self.bot.get_cog(self.qualified_name).walk_commands()
        ]:
            view = ui.Confirm()
            await view.send(
                message="Invalid argument! Show help command?",
                channel=ctx.channel,
                author=ctx.author,
                timeout=10,
            )
            await view.wait()
            if view.value != ui.ConfirmResponse.CONFIRMED:
                return
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

    @util.with_typing
    @set_group.command(
        name="game", description="Sets the game of the bot", usage="[game-name]"
    )
    async def set_game(self, ctx, *, game_name: str):
        """Sets the bot's game (activity) by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            game_name (str): the name of the game
        """
        await ctx.bot.change_presence(activity=discord.Game(name=game_name))
        await auxiliary.send_confirm_embed(
            message=f"Successfully set game to: *{game_name}*", channel=ctx.channel
        )

    @util.with_typing
    @set_group.command(
        name="nick", description="Sets the nick of the bot", usage="[nickname]"
    )
    async def set_nick(self, ctx, *, nick: str):
        """Sets the bot's nick by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            nick (str): the bot nickname
        """
        await ctx.message.guild.me.edit(nick=nick)
        await auxiliary.send_confirm_embed(
            message=f"Successfully set nick to: *{nick}*", channel=ctx.channel
        )

    @commands.group(
        brief="Executes an echo bot command", description="Executes an echo bot command"
    )
    async def echo(self, ctx):
        # pylint: disable=missing-function-docstring

        # Executed if there are no/invalid args supplied
        def get_help_embed(self, command_prefix):
            # Gets commands, checks if first supplied arg is valid
            embed = discord.Embed(
                title="Incorrect/no args provided, correct command usage:"
            )

            # Loops through each command in this cog
            for command in self.bot.get_cog(self.qualified_name).walk_commands():
                if issubclass(command.__class__, commands.Group):
                    continue

                if command.full_parent_name == "":
                    syntax = f"{command_prefix}{command.name}"

                else:
                    syntax = (
                        f"{command_prefix}{command.full_parent_name} {command.name}"
                    )

                embed.color = discord.Color.green()
                embed.add_field(
                    name=f"`{syntax} {command.usage or ''}`",
                    value=command.description or "No description available",
                    inline=False,
                )

            return embed

        # Checks if no arguments were supplied
        if len(ctx.message.content.split()) < 2:
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

        # Checks whether the first given argument is valid if more than one argument is supplied
        elif ctx.message.content.split().pop(1) not in [
            command.name
            for command in self.bot.get_cog(self.qualified_name).walk_commands()
        ]:
            view = ui.Confirm()
            await view.send(
                message="Invalid argument! Show help command?",
                channel=ctx.channel,
                author=ctx.author,
                timeout=10,
            )
            await view.wait()
            if view.value != ui.ConfirmResponse.CONFIRMED:
                return
            await ctx.send(
                embed=get_help_embed(self, await self.bot.get_prefix(ctx.message))
            )

    @util.with_typing
    @echo.command(
        name="channel",
        description="Echos a message to a channel",
        usage="[channel-id] [message]",
    )
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
            await auxiliary.send_deny_embed(
                message="I couldn't find that channel", channel=ctx.channel
            )
            return

        await channel.send(content=message)

        await auxiliary.send_confirm_embed(message="Message sent", channel=ctx.channel)

    @util.with_typing
    @echo.command(
        name="user",
        description="Echos a message to a user",
        usage="[user-id] [message]",
    )
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
            await auxiliary.send_deny_embed(
                message="I couldn't find that user", channel=ctx.channel
            )
            return

        await user.send(content=message)

        await auxiliary.send_confirm_embed(message="Message sent", channel=ctx.channel)

    @commands.command(
        name="restart",
        description="Restarts the bot at the container level",
        aliases=["reboot"],
    )
    async def restart(self, ctx):
        """Restarts the bot.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
        """
        await auxiliary.send_confirm_embed(
            message="Rebooting! Beep boop!", channel=ctx.channel
        )
        self.bot.irc.exit_irc()
        await self.bot.close()

    @commands.command(
        name="leave", description="Leaves a guild by ID", usage="[guild-id]"
    )
    async def leave(self, ctx, *, guild_id: int):
        """Leaves a guild by ID.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
            guild_id (int): the ID of the guild to leave
        """
        guild = discord.utils.get(self.bot.guilds, id=guild_id)
        if not guild:
            await auxiliary.send_deny_embed(
                message="I don't appear to be in that guild", channel=ctx.channel
            )
            return

        await guild.leave()

        await auxiliary.send_confirm_embed(
            message=f"I have left the guild: {guild.name} ({guild.id})",
            channel=ctx.channel,
        )

    @commands.command(name="bot", description="Provides bot info")
    async def get_bot_data(self, ctx):
        """Gets various data about the bot.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
        """
        embed = AdminEmbed(title=self.bot.user.name)

        embed.add_field(
            name="Started",
            value=f"{self.bot.startup_time} UTC" if self.bot.startup_time else "None",
            inline=True,
        )
        embed.add_field(
            name="Latency",
            value=f"{self.bot.latency*1000} ms" if self.bot.latency else "None",
            inline=True,
        )
        embed.add_field(
            name="Description", value=self.bot.description or "None", inline=True
        )
        embed.add_field(
            name="Servers",
            value=", ".join(f"{guild.name} ({guild.id})" for guild in self.bot.guilds),
            inline=True,
        )
        irc_config = getattr(self.bot.file_config.main, "irc")
        if not irc_config.enable_irc:
            embed.add_field(
                name="IRC",
                value="IRC is not enabled",
                inline=True,
            )
        else:
            irc_status = self.bot.irc.get_irc_status()
            embed.add_field(
                name="IRC",
                value=f"IRC Status: `{irc_status['status']}`\n"
                + f"IRC Bot Name: `{irc_status['name']}`\n"
                + f"Channels: `{irc_status['channels']}`",
                inline=True,
            )
        try:
            repo = git.Repo(search_parent_directories=True)
            commit = repo.head.commit
            commit_hash = commit.hexsha[:7]
            commit_message = commit.message.splitlines()[0].strip()
            branch_name = repo.active_branch.name
            match = re.search(
                r"github.com[:/](.*?)/(.*?)(?:.git)?$", repo.remotes.origin.url
            )
            if match:
                repo_owner = match.group(1)
                repo_name = match.group(2)
            else:
                repo_owner = ""
                repo_name = ""

            has_differences = repo.is_dirty()

            embed.add_field(
                name="Version Info",
                value=f"Upstream: `{repo_owner}/{repo_name}/{branch_name}`\n\
                    Commit: `{commit_hash} - {commit_message}`\n\
                    Local changes made: `{has_differences}`",
                inline=False,
            )
        except Exception as exc:
            embed.add_field(
                name="Version Info",
                value=f"There was an error getting version info: {exc}",
                inline=False,
            )

        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        await ctx.send(embed=embed)

    @util.with_typing
    @commands.command(
        name="sync",
        description="Syncs slash commands",
        usage="",
    )
    async def sync_slash_commands(self, ctx):
        """A simple command to manually sync slash commands

        Args:
            ctx (commands.Context): The context in which the command was run
        """
        synced = await self.bot.tree.sync()
        await auxiliary.send_confirm_embed(
            message=f"{len(synced)}", channel=ctx.channel
        )

    @util.with_typing
    @commands.command(
        name="issue",
        aliases=["ish", "botish", "botissue"],
        description="Creates a Github issue on the configured bot repo",
        usage="[title] [description]",
    )
    async def issue(self, ctx, title: str, description: str):
        """Creates an issue in the bot's Github Repo

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the calling message
            title: the title of the issue
            description: the description of the issue
        """

        if not self.bot.file_config.main.api_keys.github:
            await auxiliary.send_deny_embed(
                message="I don't have a Github API key", channel=ctx.channel
            )
            return

        if (
            not self.bot.file_config.special.github.username
            or not self.bot.file_config.special.github.repo
        ):
            await auxiliary.send_deny_embed(
                message="I don't have a Github repo configured", channel=ctx.channel
            )
            return

        headers = {
            "Authorization": f"Bearer {self.bot.file_config.main.api_keys.github}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "text/plain",
        }

        response = await self.bot.http_call(
            "post",
            f"{self.GITHUB_API_BASE_URL}/repos/{self.bot.file_config.special.github.username}/{self.bot.file_config.special.github.repo}/issues",
            headers=headers,
            data=json.dumps({"title": title, "body": description}),
        )

        status_code = response.get("status_code")
        if status_code != 201:
            await auxiliary.send_deny_embed(
                message=f"I was unable to create your issue (status code {status_code})",
                channel=ctx.channel,
            )
            return

        issue_url = response.get("html_url")
        number = response.get("number")

        embed = AdminEmbed(title="Issue Created")
        embed.add_field(name=f"Issue #{number}", value=f"{issue_url}")
        embed.set_thumbnail(
            url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
        )

        await ctx.send(embed=embed)
