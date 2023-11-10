import discord
import ui
from base import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(Setter(bot=bot))


class Setter(cogs.BaseCog):
    ADMIN_ONLY = True

    @commands.group(
        name="set",
        brief="Executes a `set X` bot command",
        description="Executes a `set X` bot command",
    )
    async def set_group(self, ctx):
        """The bare .set command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

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
