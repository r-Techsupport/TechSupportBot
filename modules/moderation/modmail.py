"""
Runs a bot that can be messaged to create modmail threads
Unit tests: False
Config:
    File: enable_modmail, disable_thread_creation, modmail_auth_token, modmail_prefix,
          modmail_guild, modmail_forum_channel, modmail_log_channel
    Command: aliases, automatic_responses, modmail_roles, roles_to_ping, thread_creation_message
API: None
Postgresql: True
Models: ModmailBan
Commands: contact, modmail commands, modmail ban, modmail unban
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import TYPE_CHECKING, Self

import discord
import expiringdict
from discord import app_commands
from discord.ext import commands

import configuration
import ui
from core import auxiliary, cogs
from modules.moderation import rules

if TYPE_CHECKING:
    import bot


async def has_modmail_management_role(interaction: discord.Interaction) -> bool:
    """-COMMAND CHECK-
    Checks if the invoker has a modmail management role

    Args:
        interaction (discord.Interaction): The interaction calling the modmail command

    Raises:
        AppCommandError: No modmail management roles were assigned in the config
        MissingAnyRole: Invoker doesn't have a modmail role

    Returns:
        bool: Whether the invoker has a modmail management role
    """
    user_roles = getattr(interaction.user, "roles", [])
    unparsed_roles = configuration.get_config_entry(
        interaction.guild.id, "modmail_modmail_roles"
    )
    modmail_roles = []

    if not unparsed_roles:
        raise app_commands.AppCommandError(
            "No modmail roles were assigned in the config file"
        )

    # Deduplicates the list
    unparsed_roles = list(dict.fromkeys(unparsed_roles))

    # Two for loops are needed, because an array containing all modmail roles is needed for
    # the error thrown when the user doesn't have any relevant roles.
    for role_id in configuration.get_config_entry(
        interaction.guild.id, "modmail_modmail_roles"
    ):
        role = discord.utils.get(interaction.guild.roles, id=int(role_id))

        if not role:
            continue

        modmail_roles.append(role)

    if not any(role in user_roles for role in modmail_roles):
        raise app_commands.MissingAnyRole(modmail_roles)

    return True


class Modmail_bot(discord.Client):
    """The bot used to send and receive DM messages"""

    def __init__(self: Self) -> None:
        # Setup some basic varibles that will be assigned from the TS side
        self.threads_disabled: bool = False
        self.guild_id: int = None
        self.forum_channel_id: int = None

        # Setup all intents and call the discord.Client init call to start the bot
        intents = discord.Intents.all()
        intents.members = True
        super().__init__(intents=intents)

    @commands.Cog.listener()
    async def on_message(self: Self, message: discord.Message) -> None:
        """Listen to DMs, send them to handle_dm for proper handling when applicable

        Args:
            message (discord.Message): Every sent message, gets filtered to only dms
        """

        if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
            # Log all DMs regardless of what happens to them
            await Ts_client.log_DM(
                message.author,
                "Modmail",
                message.content,
            )

            # User is banned from creating modmail threads
            if await Ts_client.models.ModmailBan.query.where(
                Ts_client.models.ModmailBan.user_id == str(message.author.id)
            ).gino.first():
                await message.add_reaction("❌")
                return

            # Makes sure existing threads can still be responded to
            if message.author.id not in active_threads and self.threads_disabled:
                await message.add_reaction("❌")
                await auxiliary.send_deny_embed(
                    message="Modmail isn't accepting messages right now. "
                    + "Please try again later.",
                    channel=message.channel,
                )
                return

            # Spam protection
            if message.author.id in delayed_people:
                await message.add_reaction("🕒")
                await auxiliary.send_deny_embed(
                    message="To restrict spam, you are timed out from creating new threads. "
                    + "You are welcome to create a new thread after 24 hours since your previous"
                    + " thread's closing.",
                    channel=message.channel,
                )
                return

            # Everything looks good - handle dm properly
            await handle_dm(message, self.guild_id, self.forum_channel_id)

    @commands.Cog.listener()
    async def on_typing(
        self: Self, channel: discord.DMChannel, user: discord.User, _: datetime
    ) -> None:
        """When someone starts typing in modmails dms, start typing in the corresponding thread

        Args:
            channel (discord.DMChannel): The channel where someone started typing
            user (discord.User): The user who started typing
        """
        if isinstance(channel, discord.DMChannel) and user.id in active_threads:
            await self.get_channel(active_threads[user.id]).typing()

    @commands.Cog.listener()
    async def on_message_edit(
        self: Self, before: discord.Message, after: discord.Message
    ) -> None:
        """When someone edits a message, send the event to the appropriate thread

        Args:
            before (discord.Message): The message prior to editing
            after (discord.Message): The message after editing
        """
        if (
            isinstance(before.channel, discord.DMChannel)
            and before.author.id in active_threads
        ):
            if await Ts_client.models.ModmailBan.query.where(
                Ts_client.models.ModmailBan.user_id == str(before.author.id)
            ).gino.first():
                return

            thread = self.get_channel(active_threads[before.author.id])
            embed = discord.Embed(
                color=discord.Color.blue(),
                title="Message edit",
                description=f"Message ID: {before.id}",
            )
            embed.timestamp = datetime.utcnow()

            # This is here to save space if this listener is triggered by something other than
            # a content modification, i.e. a message being pinned
            if before.content == after.content:
                return

            # Length handling has to be here, 1024 is the limit for inividual fields
            if len(before.content) > 1016 or len(after.content) > 1016:
                embed.set_footer(
                    text="Edit was too long to send! Sending just the result instead..."
                )
                embed.description += (
                    f"\n\n**New contents:**\n```{after.content[:5975]}```"
                )

            # Length is fine, send as usual
            else:
                embed.add_field(
                    name="Before", value=f"```\n{before.content}```"
                ).add_field(name="After", value=f"```\n{after.content}```")

            await thread.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self: Self, member: discord.Member) -> None:
        """Sends a message into a thread if the addressee left

        Args:
            member (discord.Member): The member who left
        """
        if member.id in active_threads:
            thread = self.get_channel(active_threads[member.id])
            embed = discord.Embed(
                color=discord.Color.red(),
                title="Member left",
                description=f"{member.mention} has left the guild.",
            )
            await thread.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self: Self, member: discord.Member) -> None:
        """Sends a message into a thread if the addressee joined the guild with an active thread

        Args:
            member (discord.Member): The member who joined
        """
        if member.id in active_threads:
            thread = self.get_channel(active_threads[member.id])
            embed = discord.Embed(
                color=discord.Color.blue(),
                title="Member joined",
                description=f"{member.mention} has rejoined the guild.",
            )
            await thread.send(embed=embed)


# Makes the Ts_client variable a global variable
# This is so we can use the data from the main bot in the modmail bot instance
Ts_client = None

active_threads = {}  # User id: Thread id
closure_jobs = {}  # Used in timed closes
# Is a dict because expiringDict only has dictionaries... go figure
delayed_people = expiringdict.ExpiringDict(
    max_age_seconds=86400, max_len=1000  # max_len has to be set for some reason
)

# This is needed to prevent being able to open more than one thread by sending several messages
# and then clicking the confirmations really quickly
awaiting_confirmation = []

# Prepares the Modmail client
# Is started in __init__ of the modmail extension, the client is defined here
# since it is used elsewhere
Modmail_client = Modmail_bot()


async def build_attachments(
    thread: discord.Thread, attachments: list[discord.Attachment]
) -> list[discord.File]:
    """Returns a list of as many files from a message as the bot can send to the given channel

    Args:
        thread (discord.Thread): The thread the attachments are going to be sent to
                                 (To get the maximum file size)
        attachments (list[discord.Attachment]): The list of attachments to process and resend

    Returns:
        list[discord.File]: The list of file objects ready to be sent
    """
    attachments_parsed: list[discord.File] = []

    total_attachment_size = 0
    for attachment in attachments:
        # Add attachments until the max file size is reached
        if (
            total_attachment_size := total_attachment_size + attachment.size
        ) <= thread.guild.filesize_limit:
            attachments_parsed.append(await attachment.to_file())

    # The attachments were too big
    if (failed_amount := len(attachments) - len(attachments_parsed)) != 0:
        await thread.send(
            f"{failed_amount} additional attachments were detected, but were too big to send!"
        )

    return attachments_parsed


async def handle_dm(message: discord.Message, guild_id: int, forum_id: int) -> None:
    """Sends a message to the corresponding thread, creates one if needed

    Args:
        message (discord.Message): The incoming message
        guild_id (int): The ID of the guild modmail is operating in
        forum_id (int): The ID of the forum channel modmail is operating in
    """
    # The bot is not ready to handle dms yet, this should only take a few seconds after startup
    if not Ts_client or not guild_id:
        await message.channel.send(
            embed=auxiliary.generate_basic_embed(
                color=discord.Color.light_gray(),
                description="Bot is still starting, please wait...",
            )
        )
        return
    # The user already has an open thread
    if message.author.id in active_threads:
        thread = Ts_client.get_channel(active_threads[message.author.id])

        # If thread was going to be closed, cancel the task
        if thread.id in closure_jobs:
            closure_jobs[thread.id].cancel()
            del closure_jobs[thread.id]

            await thread.send(
                embed=discord.Embed(
                    color=discord.Color.red(),
                    description="Scheduled close has been cancelled.",
                )
            )

        embed = discord.Embed(color=discord.Color.blue(), description=message.content)
        embed.set_footer(text=f"Message ID: {message.id}")
        embed.timestamp = datetime.utcnow()
        if message.author.avatar:
            embed.set_author(name=message.author, icon_url=message.author.avatar.url)
        else:
            embed.set_author(
                name=message.author, icon_url=message.author.default_avatar.url
            )

        attachments = None
        if message.attachments:
            if not message.content:
                embed.description = "*<Attachment>*"

            attachments = await build_attachments(
                thread=thread, attachments=message.attachments
            )

        # This should only happen if a sticker was sent, is here so an empty message isn't sent
        if not embed.description:
            return

        await thread.send(embed=embed, files=attachments)

        await message.add_reaction("📨")

        return

    # - No thread was found, create one -

    auto_rejections = configuration.get_config_entry(
        guild_id, "modmail_automatic_rejections"
    )
    for regex in auto_rejections:
        if re.match(regex, message.content):
            await auxiliary.send_deny_embed(
                message="This message cannot be used to start a "
                + f"thread: {auto_rejections[regex]}",
                channel=message.channel,
            )
            return

    if message.author.id in awaiting_confirmation:
        await auxiliary.send_deny_embed(
            message="Please respond to the existing prompt before trying to open a new modmail"
            + " thread!",
            channel=message.channel,
        )
        return

    confirmation = ui.Confirm()
    await confirmation.send(
        message=configuration.get_config_entry(
            guild_id, "modmail_thread_creation_message"
        ),
        channel=message.channel,
        author=message.author,
    )

    awaiting_confirmation.append(message.author.id)
    await confirmation.wait()

    if confirmation.value == ui.ConfirmResponse.DENIED:
        awaiting_confirmation.remove(message.author.id)
        await auxiliary.send_deny_embed(
            message="Thread creation cancelled.",
            channel=message.channel,
        )
        return

    if confirmation.value == ui.ConfirmResponse.TIMEOUT:
        awaiting_confirmation.remove(message.author.id)
        await auxiliary.send_deny_embed(
            message="Thread confirmation prompt timed out, please hit `Confirm` or `Cancel` when "
            + "creating a new thread. You are welcome to send another message.",
            channel=message.channel,
        )
        return

    if not await create_thread(
        channel=Ts_client.get_channel(forum_id),
        user=message.author,
        source_channel=message.channel,
        message=message,
    ):
        return

    await message.add_reaction("📨")

    awaiting_confirmation.remove(message.author.id)


async def create_thread(
    channel: discord.TextChannel,
    user: discord.User,
    source_channel: discord.TextChannel | discord.DMChannel,
    message: discord.Message = None,
) -> bool:
    """Creates a thread from a DM message.
    The message is left blank when invoked by the contact command

    Args:
        channel (discord.TextChannel): The forum channel to create the thread in
        user (discord.User): The user who sent the DM or is being contacted
        source_channel (discord.TextChannel | discord.DMChannel): Used for error handling
        message (discord.Message, optional): The incoming message

    Returns:
        bool: Whether the thread was created succesfully
    """
    # --> CHECKS <--

    # These checks can be triggered on both the users and server side using .contact
    # The code adjusts the error for formatting purposes
    if user.id in active_threads:
        # Ran from a DM
        if message:
            await auxiliary.send_deny_embed(
                message="You already have an open thread!",
                channel=source_channel,
            )
        else:
            await auxiliary.send_deny_embed(
                message=f"User already has an open thread! <#{active_threads[user.id]}>",
                channel=source_channel,
            )

        return False

    # --> WELCOME MESSAGE <--
    embed = discord.Embed(color=discord.Color.blue())

    # Formatting the description of the initial message
    description = (
        f"{user.mention} was created {discord.utils.format_dt(user.created_at, 'R')}"
    )

    past_thread_count = 0
    async for thread in channel.archived_threads():
        if not thread.name.startswith("[OPEN]") and thread.name.split("|")[
            -1
        ].strip() == str(user.id):
            past_thread_count += 1

    if past_thread_count == 0:
        description += ", has **no** past threads"
    else:
        description += f", has **{past_thread_count}** past threads"

    # If the user is a member, do member specific things
    member = channel.guild.get_member(user.id)

    if member:
        description += f", joined {discord.utils.format_dt(member.joined_at, 'R')}"

        embed.add_field(name="Nickname", value=member.nick)

        role_string = "None"
        roles = []

        for role in sorted(member.roles, key=lambda x: x.position, reverse=True):
            if role.is_default():
                continue
            roles.append(role.mention)

        if roles:
            role_string = ", ".join(roles)

        embed.add_field(name="Roles", value=role_string)

    # This shouldn't be possible because to dm the bot you need to share a server
    # Is still here for safety
    else:
        description += ", is not in this server"

    # Only adds the avatar if the user has one
    if user.avatar:
        url = user.avatar.url
    else:
        url = user.default_avatar.url

    # has to be done like this because of member handling
    embed.description = description
    embed.set_author(name=user, icon_url=url)
    embed.timestamp = datetime.utcnow()
    embed.set_footer(text=f"User ID: {user.id}")

    # Handling for roles to ping, not performed if the func was invoked by the contact command
    role_string = ""
    roles_to_ping = list(
        dict.fromkeys(
            configuration.get_config_entry(channel.guild.id, "modmail_roles_to_ping")
        )
    )
    if message and roles_to_ping:
        for role_id in roles_to_ping:
            role_string += f"<@&{role_id}> "

    # --> THREAD CREATION <--

    # All threads in the modmail forum channel HAVE to follow this scheme as long as they start
    # with [CLOSED] or [OPEN]:
    # [STATUS] | Username | Date of creation | User id
    thread = await channel.create_thread(
        name=f"[OPEN] | {user} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {user.id}",
        embed=embed,
        content=role_string.rstrip()[:2000],
        allowed_mentions=discord.AllowedMentions(roles=True),
    )
    active_threads[user.id] = thread[0].id

    # The thread creation was invoked from an incoming message
    if message:
        # - Server side -
        embed = discord.Embed(color=discord.Color.blue(), description=message.content)
        embed.set_author(name=user, icon_url=url)
        embed.set_footer(text=f"Message ID: {message.id}")
        embed.timestamp = datetime.utcnow()

        attachments = None
        if message.attachments:
            if not message.content:
                embed.description = "*<Attachment>*"

            attachments = await build_attachments(
                thread=thread[0], attachments=message.attachments
            )

        await thread[0].send(embed=embed, files=attachments)

        # - User side -
        embed = discord.Embed(
            color=discord.Color.green(),
            description="The staff will get back to you as soon as possible.",
        )
        embed.set_author(name="Thread Created")
        embed.set_footer(text="Your message has been sent.")
        embed.timestamp = datetime.utcnow()

        await message.author.send(embed=embed)

        # - Auto responses -
        automatic_responses = configuration.get_config_entry(
            channel.guild.id, "modmail_automatic_responses"
        )
        for regex in automatic_responses:
            if re.match(regex, message.content):
                await reply_to_thread(
                    raw_contents=automatic_responses[regex],
                    msg_author=message.author,
                    msg_attachments=message.attachments,
                    thread=thread[0],
                    anonymous=True,
                    automatic=True,
                )
                return True

    return True


async def reply_to_thread(
    raw_contents: str,
    msg_author: discord.Member,
    msg_attachments: list[discord.Attachment],
    thread: discord.Thread,
    anonymous: bool,
    automatic: bool = False,
) -> None:
    """Replies to a modmail thread on both the dm side and the modmail thread side

    Args:
        raw_contents (str): The raw content string
        msg_author (discord.Member): The member who has sent this message
        msg_attachments (list[discord.Attachment]): A list of attachments to send with the message
        thread (discord.Thread): The thread to reply to
        anonymous (bool): Whether to reply anonymously
        automatic (bool, optional): Whether this response was automatic
    """
    # If thread was going to be closed, cancel the task
    if thread.id in closure_jobs:
        closure_jobs[thread.id].cancel()
        del closure_jobs[thread.id]

        await thread.send(
            embed=discord.Embed(
                color=discord.Color.red(),
                description="Scheduled close has been cancelled.",
            )
        )

    # Gets the user from the guild instead of just looking for them by the id, because modmail
    # can't contact users it doesn't share a guild with. Acts as protection for people who left.
    target_member = discord.utils.get(
        thread.guild.members, id=int(thread.name.split("|")[-1].strip())
    )

    if not target_member:
        await auxiliary.send_deny_embed(
            message="This user isn't in the guild, so the message cannot be sent",
            channel=thread,
        )
        return

    # - Modmail thread side -
    embed = discord.Embed(color=discord.Color.green())
    # if there are any attachments sent, this will be changed to a list of files
    attachments = None
    # The attachments that will be sent to the user, has to be remade since they become invlaid
    # after being sent to the thread
    user_attachments = None

    if raw_contents:
        embed.description = raw_contents

    # Makes sure an empty message won't be sent
    elif not msg_attachments:
        await auxiliary.send_deny_embed(
            message="You need to include message contents!", channel=thread
        )
        return

    # Properly handles any attachments
    if msg_attachments:
        if not raw_contents:
            embed.description = "*<Attachment>*"

        attachments = await build_attachments(
            thread=thread, attachments=msg_attachments
        )

        if not attachments:
            await auxiliary.send_deny_embed(
                message="Failed to build any attachments!", channel=thread
            )

        # No need to reconfirm
        user_attachments = await build_attachments(
            thread=thread, attachments=msg_attachments
        )

    embed.timestamp = datetime.utcnow()
    embed.set_footer(text="Response")

    if automatic:
        embed.set_author(name=thread.guild, icon_url=thread.guild.icon.url)
    elif msg_author.avatar:
        embed.set_author(name=msg_author, icon_url=msg_author.avatar.url)
    else:
        embed.set_author(name=msg_author, icon_url=msg_author.default_avatar.url)

    if automatic:
        embed.set_footer(text="[Automatic] Response")
    elif msg_author == Ts_client.user:
        embed.set_footer(text="[Automatic] Response")
    elif anonymous:
        embed.set_footer(text="[Anonymous] Response")

    # Attachments is either None or a list of files, discord can handle either
    await thread.send(embed=embed, files=attachments)

    # - User side -
    embed.set_footer(text="Response")

    if anonymous:
        embed.set_author(
            name=f"{thread.guild.name} Moderator", icon_url=thread.guild.icon.url
        )

    # Refetches the user from modmails client so it can reply to it instead of TS
    user = Modmail_client.get_user(target_member.id)

    # Attachments is either None or a list of files, discord can handle either
    await user.send(embed=embed, files=user_attachments)


async def close_thread(
    thread: discord.Thread,
    silent: bool,
    timed: bool,
    log_channel: discord.TextChannel,
    closed_by: discord.User,
) -> None:
    """Closes a thread instantly or with a delay

    Args:
        thread (discord.Thread): The thread to close
        silent (bool): Whether to send a closure message to the user
        timed (bool): Whether to wait 5 minutes before closing
        log_channel (discord.TextChannel): The channel to send the closure message to
        closed_by (discord.User): The person who closed the thread
    """
    user_id = int(thread.name.split("|")[-1].strip())
    user = Modmail_client.get_user(user_id)

    # Waits 5 minutes before closing, below is only executed when func was run as an asyncio job
    if timed:
        embed = discord.Embed(
            color=discord.Color.red(),
            description="This thread will close in 5 minutes.",
        )

        embed.set_author(name="Scheduled close")
        embed.set_footer(
            text="Closing will be cancelled if a message is sent, or if the command is run again."
        )
        embed.timestamp = datetime.utcnow()

        await thread.send(embed=embed)

        await asyncio.sleep(300)

    # - Actually starts closing the thread -

    # Removes closure job from queue if it's there
    if thread.id in closure_jobs:
        # Makes sure the close job doesn't kill itself
        if not timed:
            closure_jobs[thread.id].cancel()

        del closure_jobs[thread.id]

    # Archives and locks the thread
    if silent:
        await thread.send(
            embed=auxiliary.generate_basic_embed(
                color=discord.Color.red(),
                title="Thread Silently Closed.",
                description="",
            )
        )
    else:
        await thread.send(
            embed=auxiliary.generate_basic_embed(
                color=discord.Color.red(),
                title="Thread Closed.",
                description="",
            )
        )

    await thread.edit(
        name=f"[CLOSED] {thread.name[7:]}",
        archived=True,
        locked=True,
    )

    await log_closure(thread, user_id, log_channel, closed_by, silent)

    # User has left the guild
    if not user:
        del active_threads[user_id]

        # No value needed, just has to exist in the dictionary
        delayed_people[user_id] = ""
        return

    # User can't be None anymore
    del active_threads[user.id]

    # No value needed, just has to exist in the dictionary
    delayed_people[user.id] = ""

    if silent:
        return

    # Sends the closure message to the user
    embed = discord.Embed(
        color=discord.Color.light_gray(),
        description="Please wait 24 hours before creating a new one.",
    )
    embed.set_author(name="Thread Closed")
    embed.timestamp = datetime.utcnow()

    await user.send(embed=embed)


async def log_closure(
    thread: discord.Thread,
    user_id: int,
    log_channel: discord.TextChannel,
    closed_by: discord.User,
    silent: bool,
) -> None:
    """Sends a closure message to the log channel

    Args:
        thread (discord.Thread): The thread that got closed
        user_id (int): The id of the person who created the thread, not an user object to
                             be able to include the ID even if the user leaves the guild
        log_channel (discord.TextChannel): The log channel to send the closure message to
        closed_by (discord.User): The person who closed the thread
        silent (bool): Whether the thread was closed silently
    """
    user = Modmail_client.get_user(user_id)

    if not user:
        embed = discord.Embed(
            color=discord.Color.red(),
            description=f"<#{thread.id}>",
            title=f"<User has left the guild> `{user_id}`",
        )
    else:
        embed = discord.Embed(
            color=discord.Color.red(),
            description=f"<#{thread.id}>",
            title=f"{user.name} `{user.id}`",
        )

    if silent:
        embed.set_footer(
            icon_url=closed_by.avatar.url,
            text=f"Thread silently closed by {closed_by.name}",
        )
    else:
        embed.set_footer(
            icon_url=closed_by.avatar.url,
            text=f"Thread closed by {closed_by.name}",
        )
    embed.timestamp = datetime.utcnow()

    await log_channel.send(embed=embed)


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Modmail plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to

    Raises:
        AttributeError: Raised if modmail is disabled
    """

    # Only runs if modmail is enabled
    if not bot.file_config.modmail_config.enable_modmail:
        # Raising an exception makes the extension loading mark as failed, this is surprisingly
        # the most reliable way to ensure the modmail bot or code doesn't run
        raise AttributeError("Modmail was not loaded because it's disabled")

    await bot.add_cog(Modmail(bot=bot))


class Modmail(cogs.BaseCog):
    """The modmail cog class

    Args:
        bot (bot.TechSupportBot): The main TS bot object to be stored in modmail

    Attributes:
        modmail_commands (app_commands.Group): The group for the /modmail commands
        modmail_thread_commands (app_commands.Group): The sub-group for /modmail thread
    """

    modmail_commands: app_commands.Group = app_commands.Group(
        name="modmail", description="The group of modmail commands"
    )

    modmail_thread_commands: app_commands.Group = app_commands.Group(
        name="thread",
        description="Modmail commands specific to use in threads",
        parent=modmail_commands,
    )

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        # Init is used to make variables global so they can be used on the modmail side
        super().__init__(bot=bot)

        # Makes the TS client available globally for creating threads and populating them with info
        # pylint: disable=W0603
        global Ts_client
        Ts_client = bot
        Ts_client.loop.create_task(
            Modmail_client.start(bot.file_config.modmail_config.modmail_auth_token)
        )
        Modmail_client.threads_disabled = (
            bot.file_config.modmail_config.disable_thread_creation
        )
        Modmail_client.guild_id = str(bot.file_config.modmail_config.modmail_guild)
        Modmail_client.forum_channel_id = int(
            bot.file_config.modmail_config.modmail_forum_channel
        )

        # Finally, makes the TS client available from within the Modmail extension class once again
        self.prefix = bot.file_config.modmail_config.modmail_prefix
        self.bot = bot

    async def handle_reboot(self: Self) -> None:
        """Ran when the bot is restarted"""
        await Modmail_client.close()

    async def preconfig(self: Self) -> None:
        """Fetches modmail threads once ready"""
        self.modmail_forum = await self.bot.fetch_channel(
            int(self.bot.file_config.modmail_config.modmail_forum_channel)
        )

        # Populates the currently active threads
        for thread in self.modmail_forum.threads:
            if thread.name.startswith("[OPEN]"):
                # [status, username, date, id]
                active_threads[int(thread.name.split(" | ")[3])] = thread.id

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="aliases",
        description="Lists all existing modmail aliases",
    )
    async def list_aliases(self: Self, interaction: discord.Interaction) -> None:
        """Lists all existing modmail aliases

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        # Checks if the command was an alias
        aliases = configuration.get_config_entry(
            interaction.guild.id, "modmail_aliases"
        )
        if not aliases:
            embed = auxiliary.prepare_deny_embed(
                message="There are no aliases registered for this guild",
            )

            await interaction.response.send_message(embed=embed)
            return

        embed = discord.Embed(
            color=discord.Color.green(), title="Registered aliases for this guild:"
        )
        for alias in aliases:
            embed.add_field(name=f"{self.prefix}{alias}", value=aliases[alias])

        await interaction.response.send_message(embed=embed)

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="ban",
        description="Bans a user from creating future modmail threads",
    )
    async def modmail_ban(
        self: Self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """Bans a user from creating future modmail threads

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.User): The user to ban
        """
        if await self.bot.models.ModmailBan.query.where(
            self.bot.models.ModmailBan.user_id == str(user.id)
        ).gino.first():
            embed = auxiliary.prepare_deny_embed(
                message=f"{user.mention} is already banned!"
            )
            await interaction.response.send_message(embed=embed)
            return

        # Checking against the user to see if they have the roles specified in the config
        user_roles = getattr(user, "roles", [])
        unparsed_roles = configuration.get_config_entry(
            interaction.guild.id, "modmail_modmail_roles"
        )
        modmail_roles = list(dict.fromkeys(unparsed_roles))

        # No error has to be thrown if unparsed_roles is None, it's already checked in
        # has_modmail_management_role

        # Gets permitted roles
        for role_id in unparsed_roles:
            modmail_role = discord.utils.get(interaction.guild.roles, id=int(role_id))
            if not modmail_role:
                continue

            modmail_roles.append(modmail_role)

        if any(role in user_roles for role in modmail_roles):
            embed = auxiliary.prepare_deny_embed(
                message="You cannot ban someone with a modmail role!",
            )
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer()
        view = ui.Confirm()
        await view.send(
            message=f"Ban {user.mention} from creating modmail threads?",
            channel=interaction.channel,
            author=interaction.user,
            interaction=interaction,
        )

        await view.wait()

        match view.value:
            case ui.ConfirmResponse.TIMEOUT:
                pass

            case ui.ConfirmResponse.DENIED:
                embed = auxiliary.prepare_deny_embed(
                    message=f"{user.mention} was NOT banned from creating modmail threads.",
                )
                await interaction.followup.send(embed=embed)
                return

            case ui.ConfirmResponse.CONFIRMED:
                await self.bot.models.ModmailBan(user_id=str(user.id)).create()

                embed = auxiliary.prepare_confirm_embed(
                    message=f"{user.mention} was successfully banned from creating future modmail"
                    + " threads.",
                )
                await interaction.followup.send(embed=embed)
                return

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="contact",
        description="Creates a modmail thread with a user",
    )
    async def contact(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        message: str = "",
    ) -> None:
        """Opens a modmail thread with a person of your choice

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.Member): The user to start a thread with
            message (str): An initial message to start the thread with
        """
        if user.bot:
            embed = auxiliary.prepare_deny_embed(
                message="I only talk to other bots using 0s and 1s!",
            )
            await interaction.response.send_message(embed=embed)
            return

        if user.id in active_threads:
            embed = auxiliary.prepare_deny_embed(
                message=f"User already has an open thread! <#{active_threads[user.id]}>",
            )
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer()
        confirmation = ui.Confirm()
        await confirmation.send(
            message=(f"Create a new modmail thread with {user.mention}?"),
            channel=interaction.channel,
            author=interaction.user,
            interaction=interaction,
        )

        await confirmation.wait()

        match confirmation.value:
            case ui.ConfirmResponse.TIMEOUT:
                pass

            case ui.ConfirmResponse.DENIED:
                embed = auxiliary.prepare_deny_embed(
                    message="The thread was not created.",
                )
                await interaction.followup.send(embed=embed)

            case ui.ConfirmResponse.CONFIRMED:
                # Makes sure the user can reply if they were timed out from creating threads
                if user.id in delayed_people:
                    del delayed_people[user.id]

                if await create_thread(
                    channel=self.modmail_forum,
                    user=user,
                    source_channel=interaction.channel,
                ):
                    embed = auxiliary.prepare_confirm_embed(
                        message=(
                            "Thread successfully created! "
                            f"{self.bot.get_channel(active_threads[user.id]).mention}"
                        )
                    )
                    await interaction.followup.send(embed=embed)

                if message:
                    await reply_to_thread(
                        raw_contents=message,
                        msg_author=interaction.user,
                        msg_attachments=[],
                        thread=self.bot.get_channel(active_threads[user.id]),
                        anonymous=True,
                    )

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="list-bans",
        description="Lists the users who are banned from using modmail",
    )
    async def modmail_list_bans(self: Self, interaction: discord.Interaction) -> None:
        """Lists the users who are banned from using modmail

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        bans = await self.bot.models.ModmailBan.query.gino.all()
        if not bans:
            embed = auxiliary.prepare_deny_embed(
                message="There are no modmail bans",
            )
            await interaction.response.send_message(embed=embed)
            return

        embed_description = ""

        for ban in bans:
            user: discord.User = await self.bot.fetch_user(ban.user_id)
            embed_description += f"{user.mention} - `{user}`\n"

        embed: discord.Embed = discord.Embed(
            color=discord.Color.green(),
            title="Modmail Bans:",
            description=embed_description,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="selfcontact",
        description="Creates a modmail thread with yourself, doesn't ping anyone when doing so",
    )
    async def selfcontact(
        self: Self,
        interaction: discord.Interaction,
        message: str = "",
    ) -> None:
        """Opens a modmail thread with the invoker of the thread.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            message (str): An initial message to start the thread with. Defaults to ""
        """
        if interaction.user.id in active_threads:
            embed = auxiliary.prepare_deny_embed(
                message=(
                    "You already have an open thread! "
                    f"<#{active_threads[interaction.user.id]}>",
                )
            )
            await interaction.response.send_message(embed=embed)
            return

        if interaction.user.id in awaiting_confirmation:
            embed = auxiliary.prepare_deny_embed(
                message="You already have a confirmation prompt in DMs!",
            )
            await interaction.response.send_message(embed=embed)
            return

        await interaction.response.defer()
        confirmation = ui.Confirm()
        await confirmation.send(
            message=("Create a new modmail thread with yourself?"),
            channel=interaction.channel,
            author=interaction.user,
            interaction=interaction,
        )

        await confirmation.wait()

        match confirmation.value:
            case ui.ConfirmResponse.TIMEOUT:
                pass

            case ui.ConfirmResponse.DENIED:
                embed = auxiliary.prepare_deny_embed(
                    message="The thread was not created.",
                )
                await interaction.followup.send(embed=embed)

            case ui.ConfirmResponse.CONFIRMED:
                # Makes sure the user can reply if they were timed out from creating threads
                if interaction.user in delayed_people:
                    del delayed_people[interaction.user.id]

                if await create_thread(
                    channel=self.modmail_forum,
                    user=interaction.user,
                    source_channel=interaction.channel,
                ):
                    embed = auxiliary.prepare_confirm_embed(
                        message=(
                            f"Thread successfully created! "
                            f"{self.bot.get_channel(active_threads[interaction.user.id]).mention}"
                        ),
                    )
                    await interaction.followup.send(embed=embed)

                if message:
                    await reply_to_thread(
                        raw_contents=message,
                        msg_author=interaction.user,
                        msg_attachments=[],
                        thread=self.bot.get_channel(
                            active_threads[interaction.user.id]
                        ),
                        anonymous=True,
                    )

    @app_commands.check(has_modmail_management_role)
    @modmail_commands.command(
        name="unban",
        description="Unbans a user from creating future modmail threads",
    )
    async def modmail_unban(
        self: Self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """Unbans a user from modmail, allowing them to create future threads

        Args:
            interaction (discord.Interaction): The interaction that called this command
            user (discord.User): The user to unban
        """
        ban_entry = await self.bot.models.ModmailBan.query.where(
            self.bot.models.ModmailBan.user_id == str(user.id)
        ).gino.first()

        if not ban_entry:
            embed = auxiliary.prepare_deny_embed(
                message=f"{user.mention} is not currently banned from making modmail threads!",
            )
            await interaction.response.send_message(embed=embed)
            return

        await ban_entry.delete()

        embed = auxiliary.prepare_confirm_embed(
            message=f"{user.mention} was successfully unbanned from creating modmail threads!",
        )
        await interaction.response.send_message(embed=embed)

    def pre_thread_checks(self: Self, interaction: discord.Interaction) -> bool:
        """Checks to make sure the thread command is valid and should be executed
        This checks:
        - If the command was run in a thead
        - The thread is in the modmail channel
        - The modmail thread is open

        Args:
            interaction (discord.Interaction): The interaction that called this command

        Returns:
            bool: Whether it should be run or not
        """
        if (
            not isinstance(interaction.channel, discord.Thread)
            or interaction.channel.parent_id != self.modmail_forum.id
            or interaction.channel.name.startswith("[CLOSED]")
        ):
            return False
        return True

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="alias",
        description="Sends a specified alias as an anonymous reply in the thread",
    )
    async def thread_alias(
        self: Self, interaction: discord.Interaction, name: str
    ) -> None:
        """This sends an alias by name as an anonymous reply in the running thread.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            name (str): The name of the alias to send
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        aliases = configuration.get_config_entry(
            interaction.guild.id, "modmail_aliases"
        )
        if name not in aliases:
            embed = auxiliary.prepare_deny_embed(
                f"The alias `{name}` could not be found"
            )
            await interaction.response.send_message(embed=embed)
            return
        await interaction.response.defer()

        await reply_to_thread(
            raw_contents=aliases[name],
            msg_author=interaction.user,
            msg_attachments=[],
            thread=interaction.channel,
            anonymous=True,
        )

        embed = auxiliary.prepare_confirm_embed("Message sent successfully")
        await interaction.response.send_message(embed=embed)

    @thread_alias.autocomplete("name")
    async def alias_calling_autocomplete(
        self: Self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """This runs autocomplete for the thread alias function

        Args:
            interaction (discord.Interaction): The interaction creating the command
            current (str): The current text in the alias name field

        Returns:
            list[app_commands.Choice[str]]: The list of options proposed to the user
        """
        aliases = configuration.get_config_entry(
            interaction.guild.id, "modmail_aliases"
        )

        return [
            app_commands.Choice(name=alias, value=alias)
            for alias in aliases
            if current.lower() in alias.lower()
        ][:10]

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="close",
        description="Instantly closes a modmail thead",
    )
    async def thread_close(self: Self, interaction: discord.Interaction) -> None:
        """This close a modmail thread and sends a notice to the user

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        modmail_log_channel = int(
            self.bot.file_config.modmail_config.modmail_log_channel
        )

        embed = auxiliary.prepare_confirm_embed("Thread closed successfully")
        await interaction.response.send_message(embed=embed)

        await close_thread(
            thread=interaction.channel,
            silent=False,
            timed=False,
            log_channel=self.bot.get_channel(modmail_log_channel),
            closed_by=interaction.user,
        )

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="sclose",
        description="Instantly closes a modmail thead silently",
    )
    async def thread_sclose(self: Self, interaction: discord.Interaction) -> None:
        """This close a modmail thread and does not send a notice to the user

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        modmail_log_channel = int(
            self.bot.file_config.modmail_config.modmail_log_channel
        )

        embed = auxiliary.prepare_confirm_embed("Thread closed successfully")
        await interaction.response.send_message(embed=embed)

        await close_thread(
            thread=interaction.channel,
            silent=True,
            timed=False,
            log_channel=self.bot.get_channel(modmail_log_channel),
            closed_by=interaction.user,
        )

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="tclose",
        description="Closes a modmail thread after 5 minutes, and sends a message to the user",
    )
    async def thread_tclose(self: Self, interaction: discord.Interaction) -> None:
        """This close a modmail thread after 5 minutes, and sends a message to the user

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        modmail_log_channel = int(
            self.bot.file_config.modmail_config.modmail_log_channel
        )

        if interaction.channel.id in closure_jobs:
            closure_jobs[interaction.channel.id].cancel()
            del closure_jobs[interaction.channel.id]

            await interaction.response.send_message(
                embed=discord.Embed(
                    color=discord.Color.red(),
                    description="Scheduled close has been cancelled.",
                )
            )
            return

        embed = auxiliary.prepare_confirm_embed(
            "Thread queued for closure successfully"
        )
        await interaction.response.send_message(embed=embed)

        closure_jobs[interaction.channel.id] = asyncio.create_task(
            close_thread(
                thread=interaction.channel,
                silent=False,
                timed=True,
                log_channel=self.bot.get_channel(modmail_log_channel),
                closed_by=interaction.user,
            )
        )

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="tsclose",
        description="Silently closes a modmail thread after 5 minutes",
    )
    async def thread_tsclose(self: Self, interaction: discord.Interaction) -> None:
        """This close a modmail thread after 5 minutes, and does not send a message to the user

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        modmail_log_channel = int(
            self.bot.file_config.modmail_config.modmail_log_channel
        )
        if interaction.channel.id in closure_jobs:
            closure_jobs[interaction.channel.id].cancel()
            del closure_jobs[interaction.channel.id]

            await interaction.response.send_message(
                embed=discord.Embed(
                    color=discord.Color.red(),
                    description="Scheduled close has been cancelled.",
                )
            )
            return

        embed = auxiliary.prepare_confirm_embed(
            "Thread queued for closure successfully"
        )
        await interaction.response.send_message(embed=embed)

        closure_jobs[interaction.channel.id] = asyncio.create_task(
            close_thread(
                thread=interaction.channel,
                silent=True,
                timed=True,
                log_channel=self.bot.get_channel(modmail_log_channel),
                closed_by=interaction.user,
            )
        )

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="areply",
        description="Replies to a modmail thread anonymously",
    )
    async def thread_areply(
        self: Self,
        interaction: discord.Interaction,
        message: str,
        attachment: discord.Attachment = None,
    ) -> None:
        """This replies to the current modmail thread anonymously

        Args:
            interaction (discord.Interaction): The interaction that called this command
            message (str): The message to send to the user
            attachment (discord.Attachment): If desired, an attachment to send to the user.
                Defaults to None
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        attachments_array = []
        if attachment:
            attachments_array.append(attachment)

        embed = auxiliary.prepare_confirm_embed("Message sent")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await reply_to_thread(
            raw_contents=message,
            msg_author=interaction.user,
            msg_attachments=attachments_array,
            thread=interaction.channel,
            anonymous=True,
        )

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="reply",
        description="Replies to a modmail thread",
    )
    async def thread_reply(
        self: Self,
        interaction: discord.Interaction,
        message: str,
        attachment: discord.Attachment = None,
    ) -> None:
        """This replies to the current modmail thread

        Args:
            interaction (discord.Interaction): The interaction that called this command
            message (str): The message to send to the user
            attachment (discord.Attachment): If desired, an attachment to send to the user.
                Defaults to None
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        attachments_array = []
        if attachment:
            attachments_array.append(attachment)

        embed = auxiliary.prepare_confirm_embed("Message sent")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await reply_to_thread(
            raw_contents=message,
            msg_author=interaction.user,
            msg_attachments=attachments_array,
            thread=interaction.channel,
            anonymous=False,
        )

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="factoid",
        description="Replies anonymously to a thread with the text of a given factoid",
    )
    async def thread_factoid(
        self: Self,
        interaction: discord.Interaction,
        factoid_to_send: str,
    ) -> None:
        """Replies anonymously to a thread with the text of a given factoid

        Args:
            interaction (discord.Interaction): The interaction that called this command
            factoid_to_send (str): The factoid to send to the user
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        # Ensure factoids is enabled in this guild
        if "operation.factoids" not in configuration.get_config_entry(
            interaction.guild.id, "core_enabled_extensions"
        ):
            embed = auxiliary.prepare_deny_embed(
                "Factoids are not enabled in this guild"
            )
            await interaction.response.send_message(embed=embed)
            return

        factoid = (
            await self.bot.models.Factoid.query.where(
                self.bot.models.Factoid.name == factoid_to_send.lower()
            )
            .where(self.bot.models.Factoid.guild == str(interaction.guild.id))
            .gino.first()
        )

        # Handling if the call is an alias
        if factoid and factoid.alias not in ["", None]:
            factoid = (
                await self.bot.models.Factoid.query.where(
                    self.bot.models.Factoid.name == factoid.alias
                )
                .where(self.bot.models.Factoid.guild == str(interaction.guild.id))
                .gino.first()
            )

        # Make sure the factoid exists
        if not factoid:
            embed = auxiliary.prepare_deny_embed(
                message=f"Couldn't find the factoid `{factoid_to_send}`",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Checks for restricted and disabled factoids
        if factoid.disabled or (
            factoid.restricted
            and str(self.modmail_forum.id)
            not in configuration.get_config_entry(
                interaction.guild.id, "factoids_restricted_list"
            )
        ):
            embed = auxiliary.prepare_deny_embed(
                message=f"The factoid `{factoid_to_send}` cannot be used in this channel",
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = auxiliary.prepare_confirm_embed("Message sent")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await reply_to_thread(
            raw_contents=factoid.message,
            msg_author=interaction.user,
            msg_attachments=[],
            thread=interaction.channel,
            anonymous=True,
        )

    @app_commands.check(has_modmail_management_role)
    @modmail_thread_commands.command(
        name="rule",
        description="Replies anonymously to a thread with the text of a given rule",
    )
    async def thread_rule(
        self: Self,
        interaction: discord.Interaction,
        rule_to_send: int,
    ) -> None:
        """Replies anonymously to a thread with the text of a given rule

        Args:
            interaction (discord.Interaction): The interaction that called this command
            rule_to_send (int): The rule to send to the user
        """
        if not self.pre_thread_checks(interaction):
            embed = auxiliary.prepare_deny_embed(
                "This command can only be run in an active modmail thread"
            )
            await interaction.response.send_message(embed=embed)
            return

        # Ensure factoids is enabled in this guild
        if "moderation.rules" not in configuration.get_config_entry(
            interaction.guild.id, "core_enabled_extensions"
        ):
            embed = auxiliary.prepare_deny_embed("Rules are not enabled in this guild")
            await interaction.response.send_message(embed=embed)
            return

        raw_rules = await rules.get_guild_rules(self.bot, interaction.guild)
        guild_rules = raw_rules.get("rules")

        try:
            rule = guild_rules[rule_to_send - 1]
        except IndexError:
            embed = auxiliary.prepare_deny_embed(
                message=f"Couldn't find the rule `{rule_to_send}`",
            )
            await interaction.response.send_message(embed=embed)
            return

        embed = auxiliary.prepare_confirm_embed("Message sent")
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await reply_to_thread(
            raw_contents=str(
                f"## Rule {rule_to_send}: {rule.get('name', 'None')}"
                f"\n{rule.get('description', 'None')}"
            ),
            msg_author=interaction.user,
            msg_attachments=[],
            thread=interaction.channel,
            anonymous=True,
        )
