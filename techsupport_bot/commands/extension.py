import discord
import ui
from base import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(ExtensionControl(bot=bot))


class ExtensionControl(cogs.BaseCog):
    ADMIN_ONLY = True

    @commands.group(
        name="extension",
        brief="Executes an extension bot command",
        description="Executes an extension bot command",
    )
    async def extension_group(self, ctx):
        """The bare .extension command. This does nothing but generate the help message

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

    @auxiliary.with_typing
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

    @auxiliary.with_typing
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

    @auxiliary.with_typing
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
