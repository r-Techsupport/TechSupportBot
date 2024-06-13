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
import munch
import ui
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def has_modmail_management_role(
    ctx: commands.Context, config: munch.Munch = None
) -> bool:
    """-COMMAND CHECK-
    Checks if the invoker has a modmail management role

    Args:
        ctx (commands.Context): Context used for getting the config file
        config (munch.Munch): Can be defined manually to run this without providing actual ctx

    Raises:
        CommandError: No modmail management roles were assigned in the config
        MissingAnyRole: Invoker doesn't have a modmail role

    Returns:
        bool: Whether the invoker has a modmail management role
    """
    # Only running this line of code if config isn't manually defined allows the use of
    # a discord.Message object in place of ctx
    if not config:
        config = ctx.bot.guild_configs[str(ctx.guild.id)]
    user_roles = getattr(ctx.author, "roles", [])
    unparsed_roles = config.extensions.modmail.modmail_roles.value
    modmail_roles = []

    if not unparsed_roles:
        raise commands.CommandError("No modmail roles were assigned in the config file")

    # Deduplicates the list
    unparsed_roles = list(dict.fromkeys(unparsed_roles))

    # Two for loops are needed, because an array containing all modmail roles is needed for
    # the error thrown when the user doesn't have any relevant roles.
    for role_id in config.extensions.modmail.modmail_roles.value:
        role = discord.utils.get(ctx.guild.roles, id=int(role_id))

        if not role:
            continue

        modmail_roles.append(role)

    if not any(role in user_roles for role in modmail_roles):
        raise commands.MissingAnyRole(modmail_roles)

    return True


class Modmail_bot(discord.Client):
    """The bot used to send and receive DM messages"""

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
            if message.author.id not in active_threads and DISABLE_THREAD_CREATION:
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
            await handle_dm(message)

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


# These get assigned in the __init__, are needed for inter-bot comm
# It is a goofy solution but given that this extension is only used in ONE guild, it's good enough
Ts_client = None
DISABLE_THREAD_CREATION = None
MODMAIL_FORUM_ID = None
MODMAIL_LOG_CHANNEL_ID = None
AUTOMATIC_RESPONSES = None
ROLES_TO_PING = None
THREAD_CREATION_MESSAGE = None

active_threads = {}  # User id: Thread id
closure_jobs = {}  # Used in timed closes
# Is a dict because expiringDict only has dictionaries... go figure
delayed_people = expiringdict.ExpiringDict(
    max_age_seconds=93600, max_len=1000  # max_len has to be set for some reason
)

# This is needed to prevent being able to open more than one thread by sending several messages
# and then clicking the confirmations really quickly
awaiting_confirmation = []

# Prepares the Modmail client with the Members intent used for lookups
# Is started in __init__ of the modmail exntension, the client is defined here
# since it is used elsewhere
intents = discord.Intents.default()
intents.members = True
Modmail_client = Modmail_bot(intents=intents)


async def build_attachments(
    thread: discord.Thread, message: discord.Message
) -> list[discord.File]:
    """Returns a list of as many files from a message as the bot can send to the given channel

    Args:
        thread (discord.Thread): The thread the attachments are going to be sent to
                                 (To get the maximum file size)
        message (discord.Message): The message to get the attachments from

    Returns:
        list[discord.File]: The list of file objects ready to be sent
    """
    attachments: list[discord.File] = []

    total_attachment_size = 0
    for attachment in message.attachments:
        # Add attachments until the max file size is reached
        if (
            total_attachment_size := total_attachment_size + attachment.size
        ) <= thread.guild.filesize_limit:
            attachments.append(await attachment.to_file())

    # The attachments were too big
    if (failed_amount := len(message.attachments) - len(attachments)) != 0:
        await thread.send(
            f"{failed_amount} additional attachments were detected, but were too big to send!"
        )

    return attachments


async def handle_dm(message: discord.Message) -> None:
    """Sends a message to the corresponding thread, creates one if needed

    Args:
        message (discord.Message): The incoming message
    """
    # The bot is not ready to handle dms yet, this should only take a few seconds after startup
    if not Ts_client or not MODMAIL_FORUM_ID:
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

            attachments = await build_attachments(thread=thread, message=message)

        # This should only happen if a sticker was sent, is here so an empty message isn't sent
        if not embed.description:
            return

        await thread.send(embed=embed, files=attachments)

        await message.add_reaction("📨")

        return

    # - No thread was found, create one -

    if message.author.id in awaiting_confirmation:
        await auxiliary.send_deny_embed(
            message="Please respond to the existing prompt before trying to open a new modmail"
            + " thread!",
            channel=message.channel,
        )
        return

    confirmation = ui.Confirm()
    await confirmation.send(
        message=THREAD_CREATION_MESSAGE,
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
        channel=Ts_client.get_channel(MODMAIL_FORUM_ID),
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
    source_channel: discord.TextChannel,
    message: discord.Message = None,
) -> bool:
    """Creates a thread from a DM message.
    The message is left blank when invoked by the contact command

    Args:
        channel (discord.TextChannel): The forum channel to create the thread in
        user (discord.User): The user who sent the DM or is being contacted
        source_channel (discord.TextChannel): Used for error handling
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
    if message and ROLES_TO_PING:
        for role_id in ROLES_TO_PING:
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

            attachments = await build_attachments(thread=thread[0], message=message)

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
        for regex in AUTOMATIC_RESPONSES:
            if re.match(regex, message.content):
                await reply_to_thread(
                    raw_contents=AUTOMATIC_RESPONSES[regex],
                    message=message,
                    thread=thread[0],
                    anonymous=True,
                    automatic=True,
                )
                return True

    return True


async def reply_to_thread(
    raw_contents: str,
    message: discord.Message,
    thread: discord.Thread,
    anonymous: bool,
    automatic: bool = False,
) -> None:
    """Replies to a modmail thread on both the dm side and the modmail thread side

    Args:
        raw_contents (str): The raw content string
        message (discord.Message): The outgoing message, used for attachments and author handling
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
    elif not message.attachments:
        await auxiliary.send_deny_embed(
            message="You need to include message contents!", channel=thread
        )
        return

    # Properly handles any attachments
    if message.attachments:
        if not raw_contents:
            embed.description = "*<Attachment>*"

        attachments = await build_attachments(thread=thread, message=message)

        if not attachments:
            await auxiliary.send_deny_embed(
                message="Failed to build any attachments!", channel=thread
            )

        # No need to reconfirm
        user_attachments = await build_attachments(thread=thread, message=message)

    embed.timestamp = datetime.utcnow()
    embed.set_footer(text="Response")

    if automatic:
        embed.set_author(name=thread.guild, icon_url=thread.guild.icon.url)
    elif message.author.avatar:
        embed.set_author(name=message.author, icon_url=message.author.avatar.url)
    else:
        embed.set_author(
            name=message.author, icon_url=message.author.default_avatar.url
        )

    if automatic:
        embed.set_footer(text="[Automatic] Response")
    elif message.author == Ts_client.user:
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

    config = extensionconfig.ExtensionConfig()

    config.add(
        key="aliases",
        datatype="dict",
        title="Aliases for modmail messages",
        description="Custom modmail commands to send message slices",
        default={},
    )

    config.add(
        key="automatic_responses",
        datatype="dict",
        title="Modmail autoresponses",
        description="If someone sends a message containing a key, sends its value",
        default={},
    )

    config.add(
        key="modmail_roles",
        datatype="list",
        title="Roles that can access modmail and its commands",
        description="Roles that can access modmail and its commands",
        default=[],
    )

    config.add(
        key="roles_to_ping",
        datatype="list",
        title="Roles to ping on thread creation",
        description="Roles to ping on thread creation",
        default=[],
    )

    config.add(
        key="thread_creation_message",
        datatype="str",
        title="Thread creation message",
        description="The message sent to the user when confirming a thread creation.",
        default="Create modmail thread?",
    )
    await bot.add_cog(Modmail(bot=bot))
    bot.add_extension_config("modmail", config)


class Modmail(cogs.BaseCog):
    """The modmail cog class

    Args:
        bot (bot.TechSupportBot): The main TS bot object to be stored in modmail
    """

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

        # -> This makes the configs available from the whole file, this can only be done here
        # -> thanks to modmail only being available in one guild. It is NEEDED for inter-bot comms
        # -> Pylint disables present because it bitches about using globals

        # pylint: disable=W0603
        global DISABLE_THREAD_CREATION
        DISABLE_THREAD_CREATION = bot.file_config.modmail_config.disable_thread_creation

        # pylint: disable=W0603
        global MODMAIL_FORUM_ID
        MODMAIL_FORUM_ID = int(bot.file_config.modmail_config.modmail_forum_channel)

        # pylint: disable=W0603
        global MODMAIL_LOG_CHANNEL_ID
        MODMAIL_LOG_CHANNEL_ID = int(bot.file_config.modmail_config.modmail_log_channel)

        config = bot.guild_configs[str(bot.file_config.modmail_config.modmail_guild)]

        # pylint: disable=W0603
        global AUTOMATIC_RESPONSES
        AUTOMATIC_RESPONSES = config.extensions.modmail.automatic_responses.value

        # pylint: disable=W0603
        global ROLES_TO_PING
        # dict.fromkeys() to deduplicate the list
        ROLES_TO_PING = list(
            dict.fromkeys(config.extensions.modmail.roles_to_ping.value)
        )

        # pylint: disable=W0603
        global THREAD_CREATION_MESSAGE
        THREAD_CREATION_MESSAGE = (
            config.extensions.modmail.thread_creation_message.value
        )

        # Finally, makes the TS client available from within the Modmail extension class once again
        self.prefix = bot.file_config.modmail_config.modmail_prefix
        self.bot = bot

    async def handle_reboot(self: Self) -> None:
        """Ran when the bot is restarted"""

        await Modmail_client.close()

    async def preconfig(self: Self) -> None:
        """Fetches modmail threads once ready"""
        self.modmail_forum = await self.bot.fetch_channel(MODMAIL_FORUM_ID)

        # Populates the currently active threads
        for thread in self.modmail_forum.threads:
            if thread.name.startswith("[OPEN]"):
                # [status, username, date, id]
                active_threads[int(thread.name.split(" | ")[3])] = thread.id

    @commands.Cog.listener()
    async def on_message(self: Self, message: discord.Message) -> None:
        """Processes messages sent in a modmail thread, basically a manual command handler

        Args:
            message (discord.Message): The sent message
        """
        if (
            not message.content.startswith(self.prefix)
            or not isinstance(message.channel, discord.Thread)
            or message.channel.parent_id != self.modmail_forum.id
            or message.channel.name.startswith("[CLOSED]")
            or message.author.bot
        ):
            return

        # Makes sure the person is actually allowed to run modmail commands
        config = self.bot.guild_configs[str(message.guild.id)]
        try:
            await has_modmail_management_role(message, config)
        except commands.MissingAnyRole as e:
            await auxiliary.send_deny_embed(message=f"{e}", channel=message.channel)
            return

        # Gets the content without the prefix
        content = message.content.partition(self.prefix)[2]

        # Checks if the message had a command
        match content.split()[0]:
            # - Normal closes -
            case "close":
                await close_thread(
                    thread=message.channel,
                    silent=False,
                    timed=False,
                    log_channel=self.bot.get_channel(MODMAIL_LOG_CHANNEL_ID),
                    closed_by=message.author,
                )

                return

            case "tclose":
                # If close was scheduled, cancel it
                if message.channel.id in closure_jobs:
                    closure_jobs[message.channel.id].cancel()
                    del closure_jobs[message.channel.id]

                    await message.channel.send(
                        embed=discord.Embed(
                            color=discord.Color.red(),
                            description="Scheduled close has been cancelled.",
                        )
                    )
                    return

                # I LOVE INDENTATIONS THEY ARE SO COOL
                closure_jobs[message.channel.id] = asyncio.create_task(
                    close_thread(
                        thread=message.channel,
                        silent=False,
                        timed=True,
                        log_channel=self.bot.get_channel(MODMAIL_LOG_CHANNEL_ID),
                        closed_by=message.author,
                    )
                )

            # - Silent closes -
            case "sclose":
                await close_thread(
                    thread=message.channel,
                    silent=True,
                    timed=False,
                    log_channel=self.bot.get_channel(MODMAIL_LOG_CHANNEL_ID),
                    closed_by=message.author,
                )

                return

            case "tsclose":
                # If close was scheduled, cancel it
                if message.channel.id in closure_jobs:
                    closure_jobs[message.channel.id].cancel()
                    del closure_jobs[message.channel.id]

                    await message.channel.send(
                        embed=discord.Embed(
                            color=discord.Color.red(),
                            description="Scheduled close has been cancelled.",
                        )
                    )
                    return

                closure_jobs[message.channel.id] = asyncio.create_task(
                    close_thread(
                        thread=message.channel,
                        silent=True,
                        timed=True,
                        log_channel=self.bot.get_channel(MODMAIL_LOG_CHANNEL_ID),
                        closed_by=message.author,
                    )
                )

            # - Replies -
            case "reply":
                await message.delete()
                await reply_to_thread(
                    raw_contents=content[5:],
                    message=message,
                    thread=message.channel,
                    anonymous=False,
                )
                return

            case "areply":
                await message.delete()
                await reply_to_thread(
                    raw_contents=content[6:],
                    message=message,
                    thread=message.channel,
                    anonymous=True,
                )
                return

            # Sends a factoid
            case "send":
                # Replaces \n with spaces so factoid can be called even with newlines
                query = message.content.replace("\n", " ").split(" ")[1].lower()
                factoid = (
                    await self.bot.models.Factoid.query.where(
                        self.bot.models.Factoid.name == query.lower()
                    )
                    .where(self.bot.models.Factoid.guild == str(message.guild.id))
                    .gino.first()
                )

                # Handling if the call is an alias
                if factoid and factoid.alias not in ["", None]:
                    factoid = (
                        await self.bot.models.Factoid.query.where(
                            self.bot.models.Factoid.name == factoid.alias
                        )
                        .where(self.bot.models.Factoid.guild == str(message.guild.id))
                        .gino.first()
                    )

                if not factoid:
                    await auxiliary.send_deny_embed(
                        message=f"Couldn't find the factoid `{query}`",
                        channel=message.channel,
                    )
                    return

                # Checks for restricted and disabled factoids
                config = self.bot.guild_configs[str(message.guild.id)]

                if factoid.disabled or (
                    factoid.restricted
                    and str(MODMAIL_FORUM_ID)
                    not in config.extensions.factoids.restricted_list.value
                ):
                    return

                await reply_to_thread(
                    raw_contents=factoid.message,
                    message=message,
                    thread=message.channel,
                    anonymous=True,
                )

        # Checks if the command was an alias
        aliases = config.extensions.modmail.aliases.value

        for alias in aliases:
            if alias != content.split()[0]:
                continue

            await message.delete()
            await reply_to_thread(
                raw_contents=aliases[alias],
                message=message,
                thread=message.channel,
                anonymous=True,
            )
            return

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @commands.command(
        name="contact",
        description="Creates a modmail thread with a user",
        usage="[user-to-contact]",
    )
    async def contact(self: Self, ctx: commands.Context, user: discord.User) -> None:
        """Opens a modmail thread with a person of your choice

        Args:
            ctx (commands.Context): Context of the command execution
            user (discord.User): The user to start a thread with
        """
        if user.bot:
            await auxiliary.send_deny_embed(
                message="I only talk to other bots using 0s and 1s!",
                channel=ctx.channel,
            )
            return

        if user.id in active_threads:
            await auxiliary.send_deny_embed(
                message=f"User already has an open thread! <#{active_threads[user.id]}>",
                channel=ctx.channel,
            )
            return

        confirmation = ui.Confirm()
        await confirmation.send(
            message=(f"Create a new modmail thread with {user.mention}?"),
            channel=ctx.channel,
            author=ctx.author,
        )

        await confirmation.wait()

        match confirmation.value:
            case ui.ConfirmResponse.TIMEOUT:
                pass

            case ui.ConfirmResponse.DENIED:
                await auxiliary.send_deny_embed(
                    message="The thread was not created.",
                    channel=ctx.channel,
                )

            case ui.ConfirmResponse.CONFIRMED:

                # Makes sure the user can reply if they were timed out from creating threads
                if user.id in delayed_people:
                    del delayed_people[user.id]

                if await create_thread(
                    channel=self.bot.get_channel(MODMAIL_FORUM_ID),
                    user=user,
                    source_channel=ctx.channel,
                ):

                    await auxiliary.send_confirm_embed(
                        message="Thread successfully created!", channel=ctx.channel
                    )

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @commands.command(
        name="selfcontact",
        description="Creates a modmail thread with yourself, doesn't ping anyone when doing so",
        usage="[user-to-contact]",
    )
    async def selfcontact(self: Self, ctx: commands.Context) -> None:
        """Opens a modmail thread with yourself

        Args:
            ctx (commands.Context): Context of the command execution
        """
        if ctx.author.id in active_threads:
            await auxiliary.send_deny_embed(
                message=f"You already have an open thread! <#{active_threads[ctx.author.id]}>",
                channel=ctx.channel,
            )
            return

        if ctx.author.id in awaiting_confirmation:
            await auxiliary.send_deny_embed(
                message="You already have a confirmation prompt in DMs!",
                channel=ctx.channel,
            )
            return

        confirmation = ui.Confirm()
        await confirmation.send(
            message=("Create a new modmail thread with yourself?"),
            channel=ctx.channel,
            author=ctx.author,
        )

        await confirmation.wait()

        match confirmation.value:
            case ui.ConfirmResponse.TIMEOUT:
                pass

            case ui.ConfirmResponse.DENIED:
                await auxiliary.send_deny_embed(
                    message="The thread was not created.",
                    channel=ctx.channel,
                )

            case ui.ConfirmResponse.CONFIRMED:

                # Makes sure the user can reply if they were timed out from creating threads
                if ctx.author in delayed_people:
                    del delayed_people[ctx.author.id]

                if await create_thread(
                    channel=self.bot.get_channel(MODMAIL_FORUM_ID),
                    user=ctx.author,
                    source_channel=ctx.channel,
                ):

                    await auxiliary.send_confirm_embed(
                        message="Thread successfully created!", channel=ctx.channel
                    )

    @commands.group(name="modmail")
    async def modmail(self: Self, ctx: commands.Context) -> None:
        """The bare .modmail command. This does nothing but generate the help message

        Args:
            ctx (commands.Context): The context in which the command was run in
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    def modmail_commands_list(self: Self) -> list[tuple[str, str, str, str]]:
        """
        Builds a list of commands to allow both .modmail commands and .help to use them
        Commands are sorted into a 4 part tuple:
        [0] - prefix
        [1] - command name
        [2] - command usage
        [3] - command description

        Returns:
            list[tuple[str, str, str, str]]: The list of commands,
                formatted to be added to the help menu
        """
        prefix = self.bot.file_config.modmail_config.modmail_prefix
        commands_list = [
            (prefix, "reply", "[message]", "Sends a message"),
            (prefix, "areply", "[message]", "Sends a message anonymously"),
            (prefix, "send", "[factoid]", "Sends the user a factoid"),
            (
                prefix,
                "close",
                "",
                "Closes the thread, sends the user a closure message",
            ),
            (
                prefix,
                "tclose",
                "",
                "Closes a thread in 5 minutes unless rerun or a message is sent",
            ),
            (prefix, "sclose", "", "Closes a thread without sending the user anything"),
            (
                prefix,
                "tsclose",
                "",
                (
                    "Closes a thread in 5 minutes unless rerun or a message is sent, closes "
                    "without sending the user anything"
                ),
            ),
        ]
        return commands_list

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @modmail.command(
        name="commands",
        description="Lists all commands you can use in modmail threads",
    )
    async def modmail_commands(self: Self, ctx: commands.Context) -> None:
        """Lists all commands usable in modmail threads

        Args:
            ctx (commands.Context): Context of the command execution
        """
        list_of_modmail_commands = self.modmail_commands_list()
        prefix = self.bot.file_config.modmail_config.modmail_prefix
        embed = discord.Embed(
            color=discord.Color.green(),
            description=f"*You can use these by typing `{prefix}<command>` in a modmail thread*",
            title="Modmail commands",
        )
        embed.timestamp = datetime.utcnow()

        # First three are reply commands
        for command in list_of_modmail_commands[:3]:
            embed.add_field(name=command[1], value=command[3])

        # ZWSP used to separate the replies from closes, makes the fields a bit prettier
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # Last four are closing commands
        for command in list_of_modmail_commands[3:]:
            embed.add_field(name=command[1], value=command[3])

        await ctx.send(embed=embed)

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @modmail.command(
        name="aliases",
        description="Lists all existing modmail aliases",
        usage="",
    )
    async def list_aliases(self: Self, ctx: commands.context) -> None:
        """Lists all existing modmail aliases

        Args:
            ctx (commands.context): Context of the command execution
        """

        config = self.bot.guild_configs[str(ctx.guild.id)]

        # Checks if the command was an alias
        aliases = config.extensions.modmail.aliases.value
        if not aliases:
            embed = auxiliary.generate_basic_embed(
                color=discord.Color.green(),
                description="There are no aliases registered for this guild",
            )

        for alias in aliases:
            embed = discord.Embed(
                color=discord.Color.green(), title="Registered aliases for this guild:"
            )
            embed.add_field(name=f"{self.prefix}{alias}", value=aliases[alias])

        await ctx.channel.send(embed=embed)

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @modmail.command(
        name="ban",
        description="Bans a user from creating future modmail threads",
        usage="[user-to-ban]",
    )
    async def modmail_ban(
        self: Self, ctx: commands.Context, user: discord.User
    ) -> None:
        """Bans a user from creating future modmail threads

        Args:
            ctx (commands.Context): Context of the command execution
            user (discord.User): The user to ban
        """
        if await self.bot.models.ModmailBan.query.where(
            self.bot.models.ModmailBan.user_id == str(user.id)
        ).gino.first():
            await auxiliary.send_deny_embed(
                message=f"{user.mention} is already banned!", channel=ctx.channel
            )
            return

        # Checking against the user to see if they have the roles specified in the config
        config = self.bot.guild_configs[str(ctx.guild.id)]
        user_roles = getattr(user, "roles", [])
        unparsed_roles = config.extensions.modmail.modmail_roles.value
        modmail_roles = list(dict.fromkeys(unparsed_roles))

        # No error has to be thrown if unparsed_roles is None, it's already checked in
        # has_modmail_management_role

        # Gets permitted roles
        for role_id in config.extensions.modmail.modmail_roles.value:
            modmail_role = discord.utils.get(ctx.guild.roles, id=int(role_id))
            if not modmail_role:
                continue

            modmail_roles.append(modmail_role)

        if any(role in user_roles for role in modmail_roles):
            await auxiliary.send_deny_embed(
                message="You cannot ban someone with a modmail role!",
                channel=ctx.channel,
            )
            return

        view = ui.Confirm()
        await view.send(
            message=f"Ban {user.mention} from creating modmail threads?",
            channel=ctx.channel,
            author=ctx.author,
        )

        await view.wait()

        match view.value:
            case ui.ConfirmResponse.TIMEOUT:
                pass

            case ui.ConfirmResponse.DENIED:
                await auxiliary.send_deny_embed(
                    message=f"{user.mention} was NOT banned from creating modmail threads.",
                    channel=ctx.channel,
                )
                return

            case ui.ConfirmResponse.CONFIRMED:
                await self.bot.models.ModmailBan(user_id=str(user.id)).create()

                await auxiliary.send_confirm_embed(
                    message=f"{user.mention} was successfully banned from creating future modmail"
                    + " threads.",
                    channel=ctx.channel,
                )
                return

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @modmail.command(
        name="unban",
        description="Unbans a user from creating future modmail threads",
        usage="[user-to-unban]",
    )
    async def modmail_unban(
        self: Self, ctx: commands.Context, user: discord.User
    ) -> None:
        """Opens a modmail thread with a person of your choice

        Args:
            ctx (commands.Context): Context of the command execution
            user (discord.User): The user to ban
        """
        ban_entry = await self.bot.models.ModmailBan.query.where(
            self.bot.models.ModmailBan.user_id == str(user.id)
        ).gino.first()

        if not ban_entry:
            await auxiliary.send_deny_embed(
                message=f"{user.mention} is not currently banned from making modmail threads!",
                channel=ctx.channel,
            )
            return

        await ban_entry.delete()

        await auxiliary.send_confirm_embed(
            message=f"{user.mention} was successfully unbanned from creating modmail threads!",
            channel=ctx.channel,
        )
