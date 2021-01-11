"""Cog for controlling the bot.
"""

from cogs import BasicPlugin
from discord import Forbidden
from discord.ext import commands
from utils.embed import SafeEmbed
from utils.helpers import paginate, tagged_response


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
            await tagged_response(ctx, f"Error: {error}")
            return

        if plugin_name:
            status = status_data.get(plugin_name)
            if not status:
                await tagged_response(ctx, "Plugin not found!")
                return

            await tagged_response(ctx, f"Plugin is {status}")
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

        await paginate(ctx, embeds)

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
            await tagged_response(ctx, "Invalid input")
            return

        response = ctx.bot.plugin_api.load_plugin(plugin_name)
        await tagged_response(ctx, response.message)

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
            await tagged_response(ctx, "Invalid input")
            return

        response = ctx.bot.plugin_api.unload_plugin(plugin_name)
        await tagged_response(ctx, response.message)

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
            await tagged_response(ctx, "Invalid input")
            return

        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await tagged_response(ctx, f"No such command: `{command_name}`")
            return

        if command_.enabled:
            await tagged_response(ctx, f"Command `{command_name}` is already enabled!")
            return

        command_.enabled = True
        await tagged_response(ctx, f"Successfully enabled command: `{command_name}`")

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
            await tagged_response(ctx, "Invalid input")
            return

        command_ = ctx.bot.get_command(command_name)
        if not command_:
            await tagged_response(ctx, f"No such command: `{command_name}`")
            return

        if not command_.enabled:
            await tagged_response(ctx, f"Command `{command_name}` is already disabled!")
            return

        command_.enabled = False
        await tagged_response(ctx, f"Successfully disabled command: `{command_name}`")

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
            await tagged_response(ctx, f"Successfully set game to: *{game_}*")

        else:
            await tagged_response(ctx, "I cannot play a game with no name!")

    @commands.command(name="purge", hidden=True)
    async def purge(self, ctx, *args):
        """Deletes a set number messages.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.Ctx): the context object for the message
            args [list]: the space-or-quote-delimitted args
        """
        # dat constant lookup
        targets = (
            set(user.id for user in ctx.message.mentions)
            if ctx.message.mentions
            else None
        )

        try:
            amount = int(args[-1])
        except (IndexError, ValueError):
            amount = 0

        if amount <= 0 or amount > 50:
            amount = 50

        def check(message):
            if not targets or message.author.id in targets:
                return True
            return False

        try:
            await ctx.channel.purge(limit=amount, check=check)
        except Forbidden:
            pass

        await tagged_response(
            ctx,
            f"I finished trying to delete {amount} messages",
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
            await tagged_response(ctx, "I couldn't find that channel")
            return

        message = " ".join(args)
        if not message:
            await tagged_response(ctx, "I need a message to echo")
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
            await tagged_response(ctx, "I couldn't find that user")
            return

        message = " ".join(args)
        if not message:
            await tagged_response(ctx, "I need a message to echo")
            return

        await user.send(content=message)
