"""
Commands which allow control over loaded extensions
The cog in the file is named:
    ExtensionControl

This file contains 4 commands:
    .extension status
    .extension load
    .extension unload
    .extension register
"""

import discord
import ui
from base import auxiliary, cogs, extension
from discord.ext import commands


async def setup(bot):
    """Registers the ExtensionControl Cog"""
    await bot.add_cog(ExtensionControl(bot=bot))


class ExtensionControl(cogs.BaseCog):
    """
    The class that holds the extension commands
    """

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
        await extension.extension_help(self, ctx, self.__module__[9:])

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
        extensions_status = (
            "loaded"
            if ctx.bot.extensions.get(
                f"{self.bot.EXTENSIONS_DIR_NAME}.{extension_name}"
            )
            else "unloaded"
        )
        functions_status = (
            "loaded"
            if ctx.bot.extensions.get(f"{self.bot.FUNCTIONS_DIR_NAME}.{extension_name}")
            else "unloaded"
        )
        embed = discord.Embed(
            title=f"Extension status for `{extension_name}`",
            description=f"Extension: {extensions_status}\nFunction: {functions_status}",
        )

        if functions_status == "loaded" or extensions_status == "loaded":
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
