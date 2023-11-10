import discord
import ui
from base import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(CommandControl(bot=bot))


class CommandControl(cogs.BaseCog):
    ADMIN_ONLY = True

    @commands.group(
        name="command",
        brief="Executes a commands bot command",
        description="Executes a commands bot command",
    )
    async def command_group(self, ctx):
        """The bare .command command. This does nothing but generate the help message

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

    @auxiliary.with_typing
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
