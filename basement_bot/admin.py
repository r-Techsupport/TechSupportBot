"""Cog for controlling the bot.
"""

from cogs import BasicPlugin
from discord.ext import commands
from utils.helpers import embed_from_kwargs, priv_response


class AdminControl(BasicPlugin):
    """Cog object for admin-only bot control"""

    ADMIN_ONLY = True

    HAS_CONFIG = False
    PLUGIN_NAME = __name__

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
            await priv_response(ctx, f"Error: {error}")
            return

        if plugin_name:
            if plugin_name in status_data.get("loaded", []):
                await priv_response(ctx, f"Plugin `{plugin_name}` is loaded")
            else:
                await priv_response(ctx, f"Plugin `{plugin_name}` is not loaded")
            return

        loaded = [f"`{plugin}`" for plugin in status_data.get("loaded")]
        loaded = ", ".join(loaded) if loaded else "*None*"
        unloaded = [f"`{plugin}`" for plugin in status_data.get("unloaded")]
        unloaded = ", ".join(unloaded) if unloaded else "*None*"
        disabled = [f"`{plugin}`" for plugin in status_data.get("disabled")]
        disabled = ", ".join(disabled) if disabled else "*None*"

        await priv_response(
            ctx,
            embed=embed_from_kwargs(
                title="Plugin Status",
                **{"Loaded": loaded, "Unloaded": unloaded, "Disabled": disabled},
            ),
        )

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
            await priv_response(ctx, "Invalid input")
            return

        if not plugin_name.isalpha():
            await priv_response(ctx, "Plugin name must be letters only")
            return

        response = ctx.bot.plugin_api.load_plugin(plugin_name)
        await priv_response(ctx, response.message)

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
            await priv_response(ctx, "Invalid input")
            return

        if not plugin_name.isalpha():
            await priv_response(ctx, "Plugin name must be letters only")
            return

        response = ctx.bot.plugin_api.unload_plugin(plugin_name)
        await priv_response(ctx, response.message)

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
            await priv_response(ctx, "Invalid input")
            return

        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await priv_response(ctx, f"No such command: `{command_name}`")
        else:
            if not command_.enabled:
                command_.enabled = True
                await priv_response(
                    ctx, f"Successfully enabled command: `{command_name}`"
                )
            else:
                await priv_response(
                    ctx, f"Command `{command_name}` is already enabled!"
                )

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
            await priv_response(ctx, "Invalid input")
            return

        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await priv_response(ctx, f"No such command: `{command_name}`")
        else:
            if not command_.disabled:
                command_.disabled = True
                await priv_response(
                    ctx, f"Successfully disabled command: `{command_name}`"
                )
            else:
                await priv_response(
                    ctx, f"Command `{command_name}` is already disabled!"
                )

    @commands.command(hidden=True)
    async def set_game(self, ctx, *args):
        """Sets the bot's game (activity) by name.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        game_ = " ".join(args)[:50]

        if not all(char == " " for char in game_):
            await ctx.bot.set_game(game_)
            await priv_response(ctx, f"Successfully set game to: *{game_}*")

        else:
            await priv_response(ctx, "I cannot play a game with no name!")

    @commands.command(name="delete_bot_x", hidden=True)
    async def delete_x_bot_messages(self, ctx, *args):
        """Deletes a set number of bot messages.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        if not args:
            await priv_response(ctx, "Please provide a number of messages to delete")
            return

        try:
            amount = int(args[0])
            if amount <= 0:
                amount = 1
        except Exception:
            amount = 1

        await priv_response(ctx, "Starting bot history deletion...")

        counter = 0
        async for message in ctx.channel.history(limit=500):
            if counter >= amount:
                break
            if message.author.id == ctx.bot.user.id:
                await message.delete()
                counter += 1

        await priv_response(
            ctx,
            f"I finished trying to delete {amount} of my most recent messages in that channel",
        )

    @commands.command(name="delete_all_x", hidden=True)
    async def delete_x_messages(self, ctx, *args):
        """Deletes a set number of messages.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        if not args:
            await priv_response(ctx, "Please provide a number of messages to delete")
            return

        try:
            amount = int(args[0])
            if amount <= 0:
                amount = 1
        except Exception:
            amount = 1

        await priv_response(ctx, "Starting total deletion...")

        counter = 0
        async for message in ctx.channel.history(limit=500):
            if counter >= amount:
                break
            await message.delete()
            counter += 1

        await priv_response(
            ctx,
            f"I finished trying to delete {amount} most recent messages in that channel",
        )

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
            await priv_response(ctx, "I couldn't find that channel")
            return

        message = " ".join(args)
        if not message:
            await priv_response(ctx, "I need a message to echo")
            return

        await channel.send(content=message)

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
            await priv_response(ctx, "I couldn't find that user")
            return

        message = " ".join(args)
        if not message:
            await priv_response(ctx, "I need a message to echo")
            return

        await user.send(content=message)
