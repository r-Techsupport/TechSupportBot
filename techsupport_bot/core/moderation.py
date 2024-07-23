"""This file will hold the core moderation functions. These functions will:
Do the proper moderative action and return true if successful, false if not."""

from datetime import timedelta
from typing import TYPE_CHECKING

import discord
import munch

if TYPE_CHECKING:
    import bot


async def ban_user(
    guild: discord.Guild, user: discord.User, delete_days: int, reason: str
) -> bool:
    """A very simple function that bans a given user from the passed guild

    Args:
        guild (discord.Guild): The guild to ban from
        user (discord.User): The user who needs to be banned
        delete_days (int): The numbers of days of past messages to delete
        reason (str): The reason for banning

    Returns:
        bool: True if ban was successful
    """
    # Ban the user
    await guild.ban(
        user,
        reason=reason,
        delete_message_days=delete_days,
    )
    return True


async def unban_user(guild: discord.Guild, user: discord.User, reason: str) -> bool:
    """A very simple functon that unbans a given user from the passed guild

    Args:
        guild (discord.Guild): The guild to unban from
        user (discord.User): The user to unban
        reason (str): The reason they are being unbanned

    Returns:
        bool: True if unban was successful
    """
    # Attempt to unban. If the user isn't found, return false
    try:
        await guild.unban(user, reason=reason)
        return True
    except discord.NotFound:
        return False


async def kick_user(guild: discord.Guild, user: discord.Member, reason: str) -> bool:
    """A very simple function that kicks a given user from the guild

    Args:
        guild (discord.Guild): The guild to kick from
        user (discord.Member): The member to kick from the guild
        reason (str): The reason they are being kicked

    Returns:
        bool: True if kick was successful
    """
    await guild.kick(user, reason=reason)
    return True


async def mute_user(user: discord.Member, reason: str, duration: timedelta) -> bool:
    """Times out a given user

    Args:
        user (discord.Member): The user to timeout
        reason (str): The reason they are being timed out
        duration (timedelta): How long to timeout the user for

    Returns:
        bool: True if the timeout was successful
    """
    await user.timeout(duration, reason=reason)
    return True


async def unmute_user(user: discord.Member, reason: str) -> bool:
    """Untimes out a given user.

    Args:
        user (discord.Member): The user to untimeout
        reason (str): The reason they are being untimeout

    Returns:
        bool: True if untimeout was successful
    """
    if not user.timed_out_until:
        return False
    await user.timeout(None, reason=reason)
    return True


async def warn_user(
    bot: bot.TechSupportBot, user: discord.Member, invoker: discord.Member, reason: str
) -> bool:
    """Warns a user. Does NOT check config or how many warnings a user has

    Args:
        bot (bot.TechSupportBot): The bot object to use
        user (discord.Member): The user to warn
        invoker (discord.Member): The person who warned the user
        reason (str): The reason for the warning

    Returns:
        bool: True if warning was successful
    """
    await bot.models.Warning(
        user_id=str(user.id),
        guild_id=str(invoker.guild.id),
        reason=reason,
        invoker_id=str(invoker.id),
    ).create()
    return True


async def unwarn_user(
    bot: bot.TechSupportBot, user: discord.Member, warning: str
) -> bool:
    """Removes a specific warning from a user by string

    Args:
        bot (bot.TechSupportBot): The bot object to use
        user (discord.Member): The member to remove a warning from
        warning (str): The warning to remove

    Returns:
        bool: True if unwarning was successful
    """
    query = (
        bot.models.Warning.query.where(
            bot.models.Warning.guild_id == str(user.guild.id)
        )
        .where(bot.models.Warning.reason == warning)
        .where(bot.models.Warning.user_id == str(user.id))
    )
    entry = await query.gino.first()
    if not entry:
        return False
    await entry.delete()
    return True


async def get_all_warnings(
    bot: bot.TechSupportBot, user: discord.User, guild: discord.Guild
) -> list[munch.Munch]:
    """Gets a list of all warnings for a specific user in a specific guild

    Args:
        bot (bot.TechSupportBot): The bot object to use
        user (discord.User): The user that we want warns from
        guild (discord.Guild): The guild that we want warns from

    Returns:
        list[munch.Munch]: The list of all warnings for the user/guild, if any exist
    """
    warnings = (
        await bot.models.Warning.query.where(bot.models.Warning.user_id == str(user.id))
        .where(bot.models.Warning.guild_id == str(guild.id))
        .gino.all()
    )
    return warnings


async def send_command_usage_alert(
    bot: bot.TechSupportBot,
    interaction: discord.Interaction,
    command: str,
    guild: discord.Guild,
    target: discord.Member,
) -> None:
    """Sends a usage alert to the protect events channel, if configured

    Args:
        bot (bot.TechSupportBot): The bot object to use
        interaction (discord.Interaction): The interaction that trigger the command
        command (str): The string representation of the command that was run
        guild (discord.Guild): The guild the command was run in
        target (discord.Member): The target of the command
    """

    ALERT_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/2063/PNG/512/"
        + "alert_danger_warning_notification_icon_124692.png"
    )

    config = bot.guild_configs[str(guild.id)]

    try:
        alert_channel = guild.get_channel(
            int(config.extensions.protect.alert_channel.value)
        )
    except TypeError:
        alert_channel = None

    if not alert_channel:
        return

    embed = discord.Embed(title="Protect Alert")

    embed.add_field(name="Command", value=f"`{command}`", inline=False)
    embed.add_field(
        name="Channel",
        value=f"{interaction.channel.name} ({interaction.channel.mention})",
    )
    embed.add_field(
        name="Invoking User",
        value=f"{interaction.user.display_name} ({interaction.user.mention})",
    )
    embed.add_field(
        name="Target",
        value=f"{target.display_name} ({target.mention})",
    )

    embed.set_thumbnail(url=ALERT_ICON_URL)
    embed.color = discord.Color.red()

    await alert_channel.send(embed=embed)
