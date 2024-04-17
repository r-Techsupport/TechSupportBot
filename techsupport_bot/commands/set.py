"""
Commands which allow control over various bot profile properties
The cog in the file is named:
    Setter

This file contains 2 commands:
    .set nick
    .set game
"""

import discord
from core import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Registers the ExtensionControl Cog"""
    await bot.add_cog(Setter(bot=bot))


class Setter(cogs.BaseCog):
    """
    The class that holds the set commands
    """

    @commands.check(auxiliary.bot_admin_check_context)
    @commands.group(
        name="set",
        brief="Executes a `set X` bot command",
        description="Executes a `set X` bot command",
    )
    async def set_group(self, ctx: commands.Context):
        """The bare .set command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
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

    @auxiliary.with_typing
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
