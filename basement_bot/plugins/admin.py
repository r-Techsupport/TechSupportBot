import os

from discord.ext import commands

from cogs import BasicPlugin
from utils.helpers import is_admin, priv_response, tagged_response


def setup(bot):
    bot.add_cog(AdminControl(bot))


class AdminControl(BasicPlugin):

    HAS_CONFIG = False
    PLUGIN_NAME = __name__

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
        unloaded = [f"`{plugin}`" for plugin in status_data.get("unloaded")]
        unloaded = ", ".join(unloaded) if unloaded else "*None*"
        disabled = [f"`{plugin}`" for plugin in status_data.get("disabled")]
        disabled = ", ".join(disabled) if disabled else "*None*"

        await priv_response(ctx, f"Loaded plugins: {loaded}")
        await priv_response(ctx, f"Unloaded plugins: {unloaded}")
        await priv_response(ctx, f"Disabled plugins: {disabled}")

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

        response = ctx.bot.plugin_api.load_plugin(plugin_name)
        await priv_response(ctx, response.message)

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

        response = ctx.bot.plugin_api.unload_plugin(plugin_name)
        await priv_response(ctx, response.message)

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
                await priv_response(
                    ctx, f"Command `{command_name}` is already enabled!"
                )

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
                await priv_response(
                    ctx, f"Command `{command_name}` is already disabled!"
                )

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
