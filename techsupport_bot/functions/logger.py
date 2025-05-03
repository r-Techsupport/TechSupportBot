"""Module for the logger extension for the discord bot."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
import munch
from botlogging import LogContext, LogLevel
from core import cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Logger plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
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


def get_channel_id(channel: discord.abc.GuildChannel | discord.Thread) -> int:
    """A function to get the ID of the channel that should be logged
    Will pull the parent ID if a thread is used

    Args:
        channel (discord.abc.GuildChannel | discord.Thread): The channel object

    Returns:
        int: The ID of the channel that the message was sent in
    """
    if isinstance(channel, discord.Thread):
        return channel.parent_id
    return channel.id


def get_mapped_channel_object(
    config: munch.Munch, src_channel: int
) -> discord.TextChannel:
    """Gets the destination channel object from the integer ID of the source channel
    Will return none if the channel doesn't exist in the config

    Args:
        config (munch.Munch): The guild config where the src_channel is
        src_channel (int): The ID of the source channel

    Returns:
        discord.TextChannel: The logging channel object
    """
    # Get the ID of the channel, or parent channel in the case of threads
    mapped_id = config.extensions.logger.channel_map.value.get(
        str(get_channel_id(src_channel))
    )
    if not mapped_id:
        return None

    # Get the channel object associated with the ID
    target_logging_channel = src_channel.guild.get_channel(int(mapped_id))
    if not target_logging_channel:
        return None

    return target_logging_channel


async def pre_log_checks(
    bot: bot.TechSupportBot,
    config: munch.Munch,
    src_channel: discord.abc.GuildChannel | discord.Thread,
) -> discord.TextChannel:
    """This does checks that are needed to pre log.
    It pulls the ID of the dest channel from the config, makes sure the guilds match
    And finds the TextChannel for the dest channel

    Args:
        bot (bot.TechSupportBot): The bot object
        config (munch.Munch): The config in the guild where the src channel is
        src_channel (discord.abc.GuildChannel | discord.Thread): The src channel object

    Returns:
        discord.TextChannel: The dest channel object, where the log should be sent
    """
    channel_id = get_channel_id(src_channel)

    if not str(channel_id) in config.extensions.logger.channel_map.value:
        return None

    target_logging_channel = get_mapped_channel_object(config, src_channel)
    if not target_logging_channel:
        return None

    # Don't log stuff cross-guild
    if target_logging_channel.guild.id != src_channel.guild.id:
        config = bot.guild_configs[str(src_channel.guild.id)]
        log_channel = config.get("logging_channel")
        await bot.logger.send_log(
            message="Configured channel not in associated guild - aborting log",
            level=LogLevel.WARNING,
            context=LogContext(guild=src_channel.guild, channel=src_channel),
            channel=log_channel,
        )
        return None

    return target_logging_channel


class Logger(cogs.MatchCog):
    """Class for the logger to make it to discord."""

    async def match(
        self: Self, config: munch.Munch, ctx: commands.Context, _: str
    ) -> bool:
        """Matches any message and checks if it is in a channel with a logger rule

        Args:
            config (munch.Munch): The config for the guild where the message was sent
            ctx (commands.Context): The context of the original message

        Returns:
            bool: Whether the message should be logged or not
        """
        channel_id = get_channel_id(ctx.channel)
        if not str(channel_id) in config.extensions.logger.channel_map.value:
            return False

        return True

    async def response(
        self: Self, config: munch.Munch, ctx: commands.Context, _: str, __: bool
    ) -> None:
        """If a message should be logged, this logs the message

        Args:
            config (munch.Munch): The guild config where the message was sent
            ctx (commands.Context): The context that was generated when the message was sent
        """
        target_logging_channel = await pre_log_checks(self.bot, config, ctx.channel)

        await send_message(
            self.bot,
            ctx.message,
            ctx.author,
            ctx.channel,
            target_logging_channel,
        )


async def send_message(
    bot: bot.TechSupportBot,
    message: discord.Message,
    author: discord.Member,
    src_channel: discord.abc.GuildChannel | discord.Thread,
    dest_channel: discord.TextChannel,
    content_override: str = None,
    special_flags: list[str] = [],
) -> None:
    """Makes the embed, uploads the attachements, and send a message in the dest_channel
    This will make zero checks

    Args:
        bot (bot.TechSupportBot): The bot object
        message (discord.Message): The message object to log
        author (discord.Member): The author of the message
        src_channel (discord.abc.GuildChannel | discord.Thread): The source channel where
            the initial message was sent to
        dest_channel (discord.TextChannel): The destination channel where the
            log embed will be sent
        content_override (str, optional): If supplied, the content of the message will be
            replaced with this. Defaults to None.
        special_flags (list[str], optional): If supplied, a new field on the embed will be
            added that shows this. Defaults to [].
    """
    config = bot.guild_configs[str(message.guild.id)]

    # Ensure we have attachments re-uploaded
    attachments = await build_attachments(bot, config, message)

    # Add avatar to attachments to all it to be added to the embed
    attachments.insert(0, await author.display_avatar.to_file(filename="avatar.png"))

    # Make and send the embed and files
    embed = build_embed(
        message, author, src_channel, content_override, special_flags=special_flags
    )
    await dest_channel.send(embed=embed, files=attachments[:11])


def build_embed(
    message: discord.Message,
    author: discord.Member,
    src_channel: discord.abc.GuildChannel | discord.Thread,
    content_override: str = None,
    special_flags: list[str] = [],
) -> discord.Embed:
    """Builds the logged messag embed

    Args:
        message (discord.Message): The message object to log
        author (discord.Member): The author of the message
        src_channel (discord.abc.GuildChannel | discord.Thread): The source channel where
            the initial message was sent to
        dest_channel (discord.TextChannel): The destination channel where the
            log embed will be sent
        content_override (str, optional): If supplied, the content of the message will be
            replaced with this. Defaults to None.
        special_flags (list[str], optional): If supplied, a new field on the embed will be
            added that shows this. Defaults to [].

    Returns:
        discord.Embed: The prepared embed ready to send to the log channel
    """
    embed = discord.Embed()

    # Set basic items
    embed.color = discord.Color.greyple()
    embed.timestamp = datetime.datetime.utcnow()

    # Add the message content
    embed.title = "Content"
    print_content = content_override

    if not content_override:
        print_content = getattr(message, "clean_content", "No content")

    embed.description = print_content
    if len(embed.description) == 0:
        embed.description = "No content"

    # Add the channel/thread name
    main_channel = getattr(src_channel, "parent", src_channel)
    embed.add_field(
        name="Channel",
        value=f"{main_channel.name} ({main_channel.mention})",
    )
    if isinstance(src_channel, discord.Thread):
        embed.add_field(
            name="Thread",
            value=f"{src_channel.name} ({src_channel.mention})",
        )

    # Add username, display name, and nickname
    embed.add_field(
        name="Display Name", value=getattr(author, "display_name", "Unknown")
    )
    if getattr(author, "nick", False):
        embed.add_field(
            name="Global Name", value=getattr(author, "global_name", "Unknown")
        )
    embed.add_field(name="Name", value=getattr(author, "name", "Unknown"))

    # Add roles
    embed.add_field(
        name="Roles",
        value=", ".join(generate_role_list(author)),
    )

    # Flags
    if special_flags:
        embed.add_field(name="Flags", value=", ".join(special_flags))

    # Add avatar
    embed.set_thumbnail(url="attachment://avatar.png")

    # Add footer with IDs for better searchings
    embed.set_footer(text=f"Author ID: {author.id} • Message ID: {message.id}")

    return embed


def generate_role_list(author: discord.Member) -> list[str]:
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
    bot: bot.TechSupportBot, config: munch.Munch, message: discord.Message
) -> list[discord.File]:
    """Reuploads and builds a list of attachments to send along side the embed

    Args:
        bot (bot.TechSupportBot): the bot object
        config (munch.Munch): The config from the guild
        message (discord.Message): The message object to log

    Returns:
        list[discord.File]: The list of file objects ready to be sent
    """
    attachments: list[discord.File] = []
    if message.attachments:
        total_attachment_size = 0
        for attch in message.attachments:
            if (
                total_attachment_size := total_attachment_size + attch.size
            ) <= message.guild.filesize_limit:
                attachments.append(await attch.to_file())
        if (lf := len(message.attachments) - len(attachments)) != 0:
            log_channel = config.get("logging_channel")
            await bot.logger.send_log(
                message=(
                    f"Logger did not reupload {lf} file(s) due to file size limit"
                    f" on message {message.id} in channel {message.channel.name}."
                ),
                level=LogLevel.WARNING,
                channel=log_channel,
                context=LogContext(guild=message.guild, channel=message.channel),
            )
    return attachments
