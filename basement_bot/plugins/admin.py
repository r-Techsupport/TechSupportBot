import os

from discord.ext import commands

from utils.helpers import is_admin, priv_response, tagged_response


def setup(bot):
    bot.add_command(plugin)
    bot.add_command(set_command)
    bot.add_command(game)
    bot.add_command(restart)


@commands.check(is_admin)
@commands.command(name="plugin", hidden=True)
async def plugin(ctx, *args):
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
@commands.command(name="command", hidden=True)
async def set_command(ctx, *args):
    option = args[0].lower() if args else None
    command_name = args[1] if len(args) > 1 else None
    if not option or not command_name:
        await priv_response(ctx, "Invalid input - type `.help command` for assistance")
        return

    command_ = ctx.bot.get_command(command_name)
    if not command_:
        await priv_response(ctx, f"No such command: `{command_name}`")
        return

    if option == "enable":
        command_.enabled = True
    elif option == "disable":
        command_.enabled = False

    await priv_response(ctx, f"Successfully {option}d command: `{command_name}`")


@commands.check(is_admin)
@commands.command(name="game", hidden=True)
async def game(ctx, *args):
    game_ = " ".join(args)[:50]

    if not all(char == " " for char in game_):
        await ctx.bot.set_game(game_)
        await priv_response(ctx, f"Successfully set game to: *{game_}*")

    else:
        await priv_response(ctx, "I cannot play a game with no name!")


@commands.check(is_admin)
@commands.command(name="restart", hidden=True)
async def restart(ctx):
    await tagged_response(ctx, "Rebooting! *Beep. boop. boop. bop.* :robot:")
    await ctx.bot.shutdown()
