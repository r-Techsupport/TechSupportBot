import os

from discord.ext import commands

from utils.helpers import is_admin, priv_response, tagged_response
from utils.cogs import BasicPlugin


def setup(bot):
    bot.add_cog(AdminControl(bot))

class AdminControl(BasicPlugin):

    @commands.check(is_admin)
    @commands.command(name="plugin_status", hidden=True)
    async def plugin_status(self, ctx, *args):
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
        available = [f"`{plugin}`" for plugin in status_data.get("available")]
        available = ", ".join(available) if available else "*None*"

        await priv_response(ctx, f"Loaded plugins: {loaded}")
        await priv_response(ctx, f"Available plugins: {available}")


    @commands.check(is_admin)
    @commands.command(name="load_plugin", hidden=True)
    async def load_plugin(self, ctx, *args):
        plugin_name = args[0].lower() if args else None
        if not plugin_name:
            await priv_response(ctx, "Invalid input")
            return
        elif not plugin_name.isalpha():
            await priv_response(ctx, "Plugin name must be letters only")
            return

        retval = ctx.bot.plugin_api.load_plugin(plugin_name)
        if retval == 0:
            await priv_response(ctx, f"Plugin `{plugin_name}` loaded successfully!")
        elif retval == 1:
            await priv_response(ctx, f"Plugin `{plugin_name}` failed to load!")
        elif retval == 126:
            await priv_response(ctx, f"Plugin `{plugin_name}` is already loaded!")


    @commands.check(is_admin)
    @commands.command(name="unload_plugin", hidden=True)
    async def unload_plugin(self, ctx, *args):
        plugin_name = args[0].lower() if args else None
        if not plugin_name:
            await priv_response(ctx, "Invalid input")
            return
        elif not plugin_name.isalpha():
            await priv_response(ctx, "Plugin name must be letters only")
            return

        retval = ctx.bot.plugin_api.unload_plugin(plugin_name)
        if retval == 0:
            await priv_response(ctx, f"Plugin `{plugin_name}` unloaded successfully!")
        elif retval == 1:
            await priv_response(ctx, f"Plugin `{plugin_name}` failed to unload!")
        elif retval == 126:
            await priv_response(ctx, f"Plugin `{plugin_name}` is not loaded!")


    @commands.check(is_admin)
    @commands.command(name="enable_command", hidden=True)
    async def enable_command(self, ctx, *args):
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
                await priv_response(ctx, f"Command `{command_name}` is already enabled!")

    @commands.check(is_admin)
    @commands.command(name="disable_command", hidden=True)
    async def disable_command(self, ctx, *args):
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
                await priv_response(ctx, f"Command `{command_name}` is already disabled!")


    @commands.check(is_admin)
    @commands.command(name="game", hidden=True)
    async def game(self, ctx, *args):
        game_ = " ".join(args)[:50]

        if not all(char == " " for char in game_):
            await ctx.bot.set_game(game_)
            await priv_response(ctx, f"Successfully set game to: *{game_}*")

        else:
            await priv_response(ctx, "I cannot play a game with no name!")


    @commands.check(is_admin)
    @commands.command(name="restart", hidden=True)
    async def restart(self, ctx):
        await tagged_response(ctx, "Rebooting! *Beep. boop. boop. bop.* :robot:")
        await ctx.bot.shutdown()
