"""This file will hold the core moderation functions. These functions will:
Do the proper moderative action and return true if successful, false if not."""

import datetime

import discord
import munch


async def ban_user(
    guild: discord.Guild, user: discord.User, delete_seconds: int, reason: str
) -> bool:
    """A very simple function that bans a given user from the passed guild

    Args:
        guild (discord.Guild): The guild to ban from
        user (discord.User): The user who needs to be banned
        delete_seconds (int): The numbers of seconds of past messages to delete
        reason (str): The reason for banning

    Returns:
        bool: True if ban was successful
    """
    # Ban the user
    await guild.ban(
        user,
        reason=reason,
        delete_message_seconds=delete_seconds,
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


async def mute_user(
    user: discord.Member, reason: str, duration: datetime.timedelta
) -> bool:
    """Times out a given user

    Args:
        user (discord.Member): The user to timeout
        reason (str): The reason they are being timed out
        duration (datetime.timedelta): How long to timeout the user for

    Returns:
        bool: True if the timeout was successful
    """
    try:
        await user.timeout(duration, reason=reason)
    except discord.Forbidden:
        return False
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
    bot_object: object,
    user: discord.Member,
    invoker: discord.Member,
    reason: str,
) -> bool:
    """Warns a user. Does NOT check config or how many warnings a user has

    Args:
        bot_object (object): The bot object to use
        user (discord.Member): The user to warn
        invoker (discord.Member): The person who warned the user
        reason (str): The reason for the warning

    Returns:
        bool: True if warning was successful
    """
    await bot_object.models.Warning(
        user_id=str(user.id),
        guild_id=str(invoker.guild.id),
        reason=reason,
        invoker_id=str(invoker.id),
    ).create()
    return True


async def unwarn_user(bot_object: object, user: discord.Member, warning: str) -> bool:
    """Removes a specific warning from a user by string

    Args:
        bot_object (object): The bot object to use
        user (discord.Member): The member to remove a warning from
        warning (str): The warning to remove

    Returns:
        bool: True if unwarning was successful
    """
    query = (
        bot_object.models.Warning.query.where(
            bot_object.models.Warning.guild_id == str(user.guild.id)
        )
        .where(bot_object.models.Warning.reason == warning)
        .where(bot_object.models.Warning.user_id == str(user.id))
    )
    entry = await query.gino.first()
    if not entry:
        return False
    await entry.delete()
    return True


async def get_all_warnings(
    bot_object: object, user: discord.User, guild: discord.Guild
) -> list[munch.Munch]:
    """Gets a list of all warnings for a specific user in a specific guild

    Args:
        bot_object (object): The bot object to use
        user (discord.User): The user that we want warns from
        guild (discord.Guild): The guild that we want warns from

    Returns:
        list[munch.Munch]: The list of all warnings for the user/guild, if any exist
    """
    warnings = (
        await bot_object.models.Warning.query.where(
            bot_object.models.Warning.user_id == str(user.id)
        )
        .where(bot_object.models.Warning.guild_id == str(guild.id))
        .order_by(bot_object.models.Warning.time.desc())
        .gino.all()
    )
    return warnings


async def get_all_notes(
    bot: object, user: discord.Member, guild: discord.Guild
) -> list[munch.Munch]:
    """Calls to the database to get a list of note database entries for a given user and guild

    Args:
        bot (object): The TS bot object to use for the database lookup
        user (discord.Member): The member to look for notes for
        guild (discord.Guild): The guild to fetch the notes from

    Returns:
        list[munch.Munch]: The list of notes on the member/guild combo.
            Will be an empty list if there are no notes
    """
    user_notes = (
        await bot.models.UserNote.query.where(
            bot.models.UserNote.user_id == str(user.id)
        )
        .where(bot.models.UserNote.guild_id == str(guild.id))
        .order_by(bot.models.UserNote.updated.desc())
        .gino.all()
    )

    return user_notes


async def send_command_usage_alert(
    bot_object: object,
    interaction: discord.Interaction,
    command: str,
    guild: discord.Guild,
    target: discord.Member = None,
) -> None:
    """Sends a usage alert to the protect events channel, if configured

    Args:
        bot_object (object): The bot object to use
        interaction (discord.Interaction): The interaction that trigger the command
        command (str): The string representation of the command that was run
        guild (discord.Guild): The guild the command was run in
        target (discord.Member): The target of the command
    """

    ALERT_ICON_URL: str = (
        "https://www.iconarchive.com/download/i76061/martz90/circle-addon2/warning.512.png"
    )

    config = bot_object.guild_configs[str(guild.id)]

    try:
        alert_channel = guild.get_channel(int(config.moderation.alert_channel))
    except TypeError:
        alert_channel = None

    if not alert_channel:
        return

    embed = discord.Embed(title="Command Usage Alert")

    embed.description = f"**Command**\n`{command}`"
    embed.add_field(
        name="Channel",
        value=f"{interaction.channel.name} ({interaction.channel.mention}) [Jump to context]"
        f"(https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/"
        f"{discord.utils.time_snowflake(datetime.datetime.utcnow())})",
    )

    embed.add_field(
        name="Invoking User",
        value=(
            f"{interaction.user.display_name} ({interaction.user.mention}, {interaction.user.id})"
        ),
    )

    if target:
        embed.add_field(
            name="Target",
            value=f"{target.display_name} ({target.mention}, {target.id})",
        )

    embed.set_thumbnail(url=ALERT_ICON_URL)
    embed.color = discord.Color.red()
    embed.timestamp = datetime.datetime.utcnow()

    await alert_channel.send(embed=embed)


async def check_if_user_banned(user: discord.User, guild: discord.Guild) -> bool:
    """Queries the given guild to find if the given discord.User is banned or not

    Args:
        user (discord.User): The user to search for being banned
        guild (discord.Guild): The guild to search the bans for

    Returns:
        bool: Whether the user is banned or not
    """

    try:
        await guild.fetch_ban(user)
    except discord.NotFound:
        return False

    return True
