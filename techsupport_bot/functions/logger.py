"""Module for the logger extension for the discord bot."""

import datetime

import discord
import munch
from botlogging import LogContext, LogLevel
from core import cogs, extensionconfig
from discord.ext import commands


async def setup(bot):
    """Adding the logger extension to the config file to get info."""
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="channel_map",
        datatype="dict",
        title="Mapping of channel ID's",
        description="Input Channel ID to Logging Channel ID mapping",
        default={},
    )

    await bot.add_cog(Logger(bot=bot, extension_name="logger"))
    bot.add_extension_config("logger", config)


class Logger(cogs.MatchCog):
    """Class for the logger to make it to discord."""

    async def match(self, config, ctx, _):
        """Method to match the logging channel to the map."""
        if isinstance(ctx.channel, discord.Thread):
            if (
                not str(ctx.channel.parent_id)
                in config.extensions.logger.channel_map.value
            ):
                return False
        else:
            if not str(ctx.channel.id) in config.extensions.logger.channel_map.value:
                return False
        return True

    async def response(self, config: munch.Munch, ctx: commands.Context, _, __) -> None:
        """Method to generate the response from the logger."""
        # Get the ID of the channel, or parent channel in the case of threads
        mapped_id = config.extensions.logger.channel_map.value.get(
            str(getattr(ctx.channel, "parent_id", ctx.channel.id))
        )
        if not mapped_id:
            return

        # Get the channel object associated with the ID
        channel = ctx.guild.get_channel(int(mapped_id))
        if not channel:
            return

        # Don't log stuff cross-guild
        if channel.guild.id != ctx.guild.id:
            config = self.bot.guild_configs[str(ctx.guild.id)]
            log_channel = config.get("logging_channel")
            await self.bot.logger.send_log(
                message="Configured channel not in associated guild - aborting log",
                level=LogLevel.WARNING,
                context=LogContext(guild=ctx.guild, channel=ctx.channel),
                channel=log_channel,
            )
            return

        # Ensure we have attachments re-uploaded
        attachments = await self.build_attachments(ctx, config)

        # Add avatar to attachments to all it to be added to the embed
        attachments.insert(
            0, await ctx.author.display_avatar.to_file(filename="avatar.png")
        )

        # Make and send the embed and files
        embed = self.build_embed(ctx)
        await channel.send(embed=embed, files=attachments[:11])

    def build_embed(self, ctx: commands.Context) -> discord.Embed:
        """Builds the logged messag embed

        Args:
            ctx (commands.Context): The context that the message to log was sent in

        Returns:
            discord.Embed: The prepared embed ready to send to the log channel
        """
        embed = discord.Embed()

        # Set basic items
        embed.color = discord.Color.greyple()
        embed.timestamp = datetime.datetime.utcnow()

        # Add the message content
        embed.title = "Content"
        embed.description = getattr(ctx.message, "clean_content", "No content")
        if len(embed.description) == 0:
            embed.description = "No content"

        # Add the channel/thread name
        main_channel = getattr(ctx.channel, "parent", ctx.channel)
        embed.add_field(
            name="Channel",
            value=f"{main_channel.name} ({main_channel.mention})",
        )
        if isinstance(ctx.channel, discord.Thread):
            embed.add_field(
                name="Thread",
                value=f"{ctx.channel.name} ({ctx.channel.mention})",
            )

        # Add username, display name, and nickname
        embed.add_field(
            name="Display Name", value=getattr(ctx.author, "display_name", "Unknown")
        )
        if getattr(ctx.author, "nick", False):
            embed.add_field(
                name="Global Name", value=getattr(ctx.author, "global_name", "Unknown")
            )
        embed.add_field(name="Name", value=getattr(ctx.author, "name", "Unknown"))

        # Add roles
        embed.add_field(
            name="Roles",
            value=", ".join(self.generate_role_list(ctx.author)),
        )

        # Add avatar
        embed.set_thumbnail(url="attachment://avatar.png")

        # Add footer with IDs for better searchings
        embed.set_footer(
            text=f"Author ID: {ctx.author.id} • Message ID: {ctx.message.id}"
        )

        return embed

    def generate_role_list(self, author: discord.Member) -> list[str]:
        """Makes a list of role names from the passed member

        Args:
            author (discord.Member): The member to get roles from

        Returns:
            list[str]: The list of roles, highest role first
        """
        if not hasattr(author, "roles"):
            return ["None"]

        roles = [role.name for role in author.roles[1:]]
        roles.reverse()

        if len(roles) == 0:
            roles = ["None"]

        return roles

    async def build_attachments(
        self, ctx: commands.Context, config: munch.Munch
    ) -> list[discord.File]:
        """Reuploads and builds a list of attachments to send along side the embed

        Args:
            ctx (commands.Context): The context the original message was sent in
            config (munch.Munch): The config from the guild

        Returns:
            list[discord.File]: The list of file objects ready to be sent
        """
        attachments: list[discord.File] = []
        if ctx.message.attachments:
            total_attachment_size = 0
            for attch in ctx.message.attachments:
                if (
                    total_attachment_size := total_attachment_size + attch.size
                ) <= ctx.filesize_limit:
                    attachments.append(await attch.to_file())
            if (lf := len(ctx.message.attachments) - len(attachments)) != 0:
                log_channel = config.get("logging_channel")
                await self.bot.logger.send_log(
                    message=(
                        f"Logger did not reupload {lf} file(s) due to file size limit"
                        f" on message {ctx.message.id} in channel {ctx.channel.name}."
                    ),
                    level=LogLevel.INFO,
                    channel=log_channel,
                    context=LogContext(guild=ctx.guild, channel=ctx.channel),
                )
        return attachments
