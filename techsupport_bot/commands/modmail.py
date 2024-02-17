"""
Runs a bot that can be messaged to create modmail threads
Unit tests: False
Config: 
    File: disable_thread_creation, modmail_auth_token, modmail_prefix, modmail_guild, 
          modmail_forum_channel, modmail_log_channel
    Command: aliases, automatic_responses, modmail_roles, roles_to_ping
API: None
Postgresql: True
Models: ModmailBan
Commands: contact, modmail ban, modmail unban
"""

import asyncio
import re
from datetime import datetime

import discord
import expiringdict
import ui
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands


async def has_modmail_management_role(ctx: commands.Context) -> bool:
    """-COMMAND CHECK-
    Checks if the invoker has a modmail management role

    Args:
        ctx (commands.Context): Context used for getting the config file

    Raises:
        commands.CommandError: No modmail management roles were assigned in the config
        commands.MissingAnyRole: Invoker doesn't have a modmail role

    Returns:
        bool: Whether the invoker has a modmail management role
    """

    config = ctx.bot.guild_configs[str(ctx.guild.id)]
    modmail_roles = []

    # Gets permitted roles
    for role_id in config.extensions.modmail.modmail_roles.value:
        role = discord.utils.get(ctx.guild.roles, id=role_id)
        if not role:
            continue
        modmail_roles.append(role)

    if not modmail_roles:
        raise commands.CommandError("No modmail roles were assigned in the config file")

    # Checking against the user to see if they have amy of the roles specified in the config
    if not any(
        modmail_role in getattr(ctx.author, "roles", [])
        for modmail_role in modmail_roles
    ):
        raise commands.MissingAnyRole(modmail_roles)

    return True


class Modmail_bot(discord.Client):
    """The bot used to send and receive DM messages"""

    async def on_message(self, message: discord.Message) -> None:
        """Listen to DMs, send them to handle_dm for proper handling when applicable

        Args:
            message (discord.Message): Every sent message, gets filtered to only dms
        """
        if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
            # User is banned from creating modmail threads
            if await Ts_client.models.ModmailBan.query.where(
                Ts_client.models.ModmailBan.user_id == str(message.author.id)
            ).gino.first():
                await message.add_reaction("❌")
                return

            # Spam protection
            if message.author.id in delayed_people:
                await message.add_reaction("🕒")
                await auxiliary.send_deny_embed(
                    message="To restrict spam, you can not open a new thread within 24 hours of"
                    + "a thread being closed. Please try again later.",
                    channel=message.channel,
                )
                return

            if DISABLE_THREAD_CREATION:
                await message.add_reaction("❌")
                await auxiliary.send_deny_embed(
                    message="Modmail isn't accepting messages right now. "
                    + "Please try again later.",
                    channel=message.channel,
                )
                return

            # Everything looks good - handle dm properly
            await handle_dm(message)

    async def on_typing(
        self, channel: discord.DMChannel, user: discord.User, _: datetime
    ):
        """When someone starts typing in modmails dms, starts typing in the corresponding thread

        Args:
            channel (discord.Channel): The channel where osmeone started typing
            user (discord.User): The user who started typing
            _ (datetime.datetime): The timestamp of when typing started, unused
        """
        if isinstance(channel, discord.DMChannel) and user.id in active_threads:
            await self.get_channel(active_threads[user.id]).typing()


# These get assigned in the __init__, are needed for inter-bot comm
# It is a goofy solution but given that this extension is only used in ONE guild, it's good enough
Ts_client = None
DISABLE_THREAD_CREATION = None
MODMAIL_FORUM_ID = None
MODMAIL_LOG_CHANNEL_ID = None
ROLES_TO_PING = None
AUTOMATIC_RESPONSES = None

active_threads = {}
closure_jobs = {}  # Used in timed closes
# Is a dict because expiringDict only has expiring dictionaries... go figure
delayed_people = expiringdict.ExpiringDict(
    max_age_seconds=93600, max_len=1000  # max_len has to be set for some reason
)

# Prepares the Modmail client with the Members intent used for lookups
# It is actually started in __init__ of the modmail command, the client is defined here
# since it is used elsewhere
intents = discord.Intents.default()
intents.members = True
Modmail_client = Modmail_bot(intents=intents)


async def build_attachments(
    thread: discord.Thread, message: discord.Message
) -> list[discord.File]:
    """Returns a list of as many files from a message as the bot can send to the given guild

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

    # Gets the modmail channel from TS-es side so it can create the thread
    modmail_channel = Ts_client.get_channel(MODMAIL_FORUM_ID)

    # The user already has an open thread
    if message.author.id in active_threads:
        await message.add_reaction("📨")

        embed = discord.Embed(color=discord.Color.blue(), description=message.content)
        embed.set_footer(text=f"Message ID: {message.id}")
        embed.timestamp = datetime.utcnow()
        if message.author.avatar:
            embed.set_author(name=message.author, icon_url=message.author.avatar.url)
        else:
            embed.set_author(
                name=message.author, icon_url=message.author.default_avatar.url
            )

        thread = Ts_client.get_channel(active_threads[message.author.id])
        await thread.send(embed=embed)

        # Handling for attachments
        if message.attachments:
            attachments = await build_attachments(thread=thread, message=message)
            # If the attachment that was sent is bigger than the bot can send, this will be empty
            if attachments:
                await thread.send(files=attachments)

        return

    # No thread was found, create one
    confirmation = ui.Confirm()
    await confirmation.send(
        message=(f"Create a Modmail thread?"),
        channel=message.channel,
        author=message.author,
    )

    await confirmation.wait()

    if (
        confirmation.value == ui.ConfirmResponse.DENIED
        or confirmation.value == ui.ConfirmResponse.TIMEOUT
    ):
        await auxiliary.send_deny_embed(
            message=f"Thread creation cancelled.",
            channel=message.channel,
        )
        return

    embed = discord.Embed(
        color=discord.Color.green(),
        description="The staff will get back to you as soon as possible.",
    )
    embed.set_author(name="Thread Created")
    embed.set_footer(text="Your message has been sent.")
    embed.timestamp = datetime.utcnow()

    await message.author.send(embed=embed)

    await create_thread(channel=modmail_channel, user=message.author, message=message)


async def create_thread(
    channel: discord.TextChannel,
    user: discord.User,
    message: discord.Message = None,
) -> None:
    """Creates a thread from a DM message
    The message is left blank when invoked by the contact command

    Args:
        channel (discord.TextChannel): The forum channel to create the thread in
        user (discord.User): The user who sent the DM or is being contacted
        message (discord.Message, optional): The incoming message
    """
    # --> WELCOME MESSAGE <--
    embed = discord.Embed(color=discord.Color.blue())

    # Formatting the description of the initial message
    description = (
        f"{user.mention} was created {discord.utils.format_dt(user.created_at, 'R')}"
    )

    past_thread_count = 0
    for thread in channel.threads:
        if not thread.name.startswith("[OPEN]") and thread.name.split("|")[
            -1
        ].strip() == str(user.id):
            past_thread_count += 1

    if past_thread_count == 0:
        description += ", has **no** past threads"
    else:
        description += f", has {past_thread_count} past threads"

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
        content=role_string.rstrip(),
    )
    active_threads[user.id] = thread[0].id

    # The thread creation was invoked from an incoming message
    if message:
        embed = discord.Embed(color=discord.Color.blue(), description=message.content)
        embed.set_author(name=user, icon_url=url)
        embed.set_footer(text=f"Message ID: {message.id}")
        embed.timestamp = datetime.utcnow()

        await thread[0].send(embed=embed)

        if message.attachments:
            attachments = await build_attachments(thread=thread[0], message=message)
            if attachments:
                await thread[0].send(files=attachments)

        for regex in AUTOMATIC_RESPONSES:
            if re.match(regex, message.content):
                await reply_to_thread(
                    content=AUTOMATIC_RESPONSES[regex],
                    author=Ts_client.user,
                    thread=thread[0],
                    anonymous=True,
                )
                return


async def reply_to_thread(
    content: str,
    author: discord.User,
    thread: discord.Thread,
    anonymous: bool,
) -> None:
    """Replies to a modmail thread on both the dm side and the modmail thread side

    Args:
        raw_content (str): The content to send
        author (discord.user): The author of the outgoing message
        thread (discord.Thread): The thread to reply to
        anonymous (bool): Whether to reply anonymously
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

    target_member = discord.utils.get(
        thread.guild.members, id=int(thread.name.split("|")[-1].strip())
    )
    # Refetches the user from modmails client so it can reply to it instead of TS
    user = Modmail_client.get_user(target_member.id)

    # - Modmail thread side -
    embed = discord.Embed(color=discord.Color.green(), description=content)
    embed.timestamp = datetime.utcnow()
    embed.set_footer(text="Response")
    if author.avatar:
        embed.set_author(name=author, icon_url=author.avatar.url)
    else:
        embed.set_author(name=author, icon_url=author.default_avatar.url)

    if author == Ts_client.user:
        embed.set_footer(text="[Automatic] Response")
    elif anonymous:
        embed.set_footer(text="[Anonymous] Response")

    await thread.send(embed=embed)

    # - User side -
    embed.set_footer(text="Response")

    if anonymous:
        embed.set_author(name="rTechSupport Moderator", icon_url=thread.guild.icon.url)

    await user.send(embed=embed)


async def close_thread(
    thread: discord.Thread,
    silent: bool,
    timed: bool,
    log_channel: discord.TextChannel,
    closed_by: discord.User,
) -> None:
    """Closes a thread instantly or on a delay

    Args:
        thread (discord.Thread): The thread to close
        silent (bool): Whether to send a closure message to the user
        timed (bool): Whether to wait 5 minutes before closing
        log_channel (discord.TextChannel): The channel to send the closure message to
        closed_by (discord.User): The person who closed the thread
    """
    user = Modmail_client.get_user(int(thread.name.split("|")[-1].strip()))

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
    del active_threads[user.id]
    # Removes closure job from queue
    if timed:
        del closure_jobs[thread.id]

    # Archives and locks the thread
    await thread.send(
        embed=auxiliary.generate_basic_embed(
            color=discord.Color.red(),
            title="Thread closed.",
            description="",
        )
    )
    await thread.edit(
        name=f"[CLOSED] {thread.name[6:]}",
        archived=True,
        locked=True,
    )

    # No value needed, just has to exist
    delayed_people[user.id] = ""

    await log_closure(thread, user, log_channel, closed_by)

    if silent:
        return

    # Sends the closure message to the user
    embed = discord.Embed(
        color=discord.Color.light_gray(),
        description="Please wait 24 hours before creating a new one.",
    )
    embed.set_author(name="Thread closed")
    embed.timestamp = datetime.utcnow()

    await user.send(embed=embed)


async def log_closure(
    thread: discord.Thread,
    user: discord.User,
    log_channel: discord.TextChannel,
    closed_by: discord.User,
) -> None:
    """Sends a closure message to the log channel

    Args:
        thread (discord.Thread): The thread that got closed
        user (discord.User): The person who created the thread
        log_channel (discord.TextChannel): The log channel to send the closure message to
        closed_by (discord.User): The person who closed the thread
    """

    embed = discord.Embed(
        color=discord.Color.red(),
        description=f"<#{thread.id}>",
        title=f"{user.name} `{user.id}`",
    )
    embed.set_footer(
        icon_url=closed_by.avatar.url,
        text=f"Thread closed by {closed_by.name}",
    )
    embed.timestamp = datetime.utcnow()

    await log_channel.send(embed=embed)


async def setup(bot):
    """Sets the modmail extension up"""
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

    await bot.add_cog(Modmail(bot=bot))
    bot.add_extension_config("modmail", config)


class Modmail(cogs.BaseCog):
    """The modmail cog class"""

    def __init__(self, bot):
        """Init is used to make variables global so they can be used on the modmail side"""

        # Makes the TS client available globally for creating threads and populating them with info
        # pylint: disable=W0603
        global Ts_client
        Ts_client = bot
        Ts_client.loop.create_task(
            Modmail_client.start(bot.file_config.modmail_config.modmail_auth_token)
        )

        # -> This makes the configs available from the whole file, this can only be done here
        # -> thanks to modmail only being available in one guild. It is NEEDED for inter-bot comms
        # -> Pylint disables because it bitches about using globals

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
        global ROLES_TO_PING
        ROLES_TO_PING = config.extensions.modmail.roles_to_ping.value

        # pylint: disable=W0603
        global AUTOMATIC_RESPONSES
        AUTOMATIC_RESPONSES = config.extensions.modmail.automatic_responses.value

        # Finally, makes the TS client available from within the Modmail class once again
        self.prefix = bot.file_config.modmail_config.modmail_prefix
        self.bot = bot

    async def handle_reboot(self):
        """Ram when the bot is restarted"""

        await Modmail_client.close()

    @commands.Cog.listener()
    async def on_ready(self):
        """Fetches the modmail channel only once ready
        Not done in preconfig because that breaks stuff for some reason?"""
        await self.bot.wait_until_ready()
        # Has to be done in here, putting into preconfig breaks stuff for some reason
        self.modmail_forum = self.bot.get_channel(MODMAIL_FORUM_ID)

        # Populates the currently active threads

        for thread in self.modmail_forum.threads:
            if thread.name.startswith("[OPEN]"):
                # [username, date, id]
                active_threads[int(thread.name.split(" | ")[3])] = thread.id

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Processes messages sent in a modmail thread, basically a manual command handler

        Args:
            message (discord.Message): The sent message

        Raises:
            commands.MissingAnyRole: When the invoker doesn't have a modmail role
        """
        if (
            not message.content.startswith(self.prefix)
            or not isinstance(message.channel, discord.Thread)
            or message.channel.parent_id != self.modmail_forum.id
            or message.channel.name.startswith("[CLOSED]")
        ):
            return
        # Makes sure the person is actually allowed to run modmail commands

        config = self.bot.guild_configs[str(message.guild.id)]
        modmail_roles = []

        # Gets permitted roles
        for role_id in config.extensions.modmail.modmail_roles.value:
            modmail_role = discord.utils.get(message.guild.roles, id=role_id)
            if not modmail_role:
                continue

            modmail_roles.append(modmail_role)

        if not any(
            modmail_role in getattr(message.author, "roles", [])
            for modmail_role in modmail_roles
        ):
            await auxiliary.send_deny_embed(
                channel=message.channel,
                message="You don't have permission to use that command!",
            )
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
                # If close was ran already, cancel it
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
                # If close was ran already, cancel it
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
                    content=content.partition(" ")[2],
                    author=message.author,
                    thread=message.channel,
                    anonymous=False,
                )
                return

            case "areply":
                await message.delete()
                await reply_to_thread(
                    content=content.partition(" ")[2],
                    author=message.author,
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

                if not factoid:
                    await auxiliary.send_deny_embed(
                        message=f"Couldn't find the factoid `{query}`",
                        channel=message.channel,
                    )
                    return

                await reply_to_thread(
                    content=factoid.message,
                    author=message.author,
                    thread=message.channel,
                    anonymous=True,
                )

        # Checks if the command was an alias
        aliases = config.extensions.modmail.aliases.value

        for alias in aliases:
            if alias != content.split()[0]:
                continue

            await message.delete()
            await reply_to_thread(aliases[alias], message.author, message.channel, True)
            return

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @commands.command(
        name="contact",
        brief="Creates a modmail thread with a user",
        usage="[user-to-contact]",
    )
    async def contact(self, ctx: commands.Context, user: discord.User):
        """Opens a modmail thread with a person of your choice

        Args:
            ctx (commands.Context): Context of the command execution
            user (discord.User): The user to start a thread with
        """
        if user.bot:
            await auxiliary.send_deny_embed(
                message="I can only talk to other bots using 1s and 0s!",
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
                await create_thread(self.bot.get_channel(MODMAIL_FORUM_ID), user=user)

                await auxiliary.send_confirm_embed(
                    message="Thread succesfully created!", channel=ctx.channel
                )

    @commands.group(name="modmail")
    async def modmail(self, ctx):
        """Method for the modmail command group."""

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @modmail.command(
        name="ban",
        brief="Bans a user from creating future modmail threads",
        usage="[user-to-ban]",
    )
    async def modmail_ban(self, ctx: commands.Context, user: discord.User):
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
        modmail_roles = []

        # Gets permitted roles
        for role_id in config.extensions.modmail.modmail_roles.value:
            modmail_role = discord.utils.get(ctx.guild.roles, id=role_id)
            if not modmail_role:
                continue

            modmail_roles.append(modmail_role)

        if any(
            modmail_role in getattr(user, "roles", []) for modmail_role in modmail_roles
        ):
            await auxiliary.send_deny_embed(
                message="You cannot ban someone with a modmail role!",
                channel=ctx.channel,
            )
            return

        view = ui.Confirm()
        await view.send(
            message=(f"Ban {user.mention} from creating modmail threads?"),
            channel=ctx.channel,
            author=ctx.author,
        )

        await view.wait()

        match view.value:
            case ui.ConfirmResponse.TIMEOUT:
                pass

            case ui.ConfirmResponse.DENIED:
                return await auxiliary.send_deny_embed(
                    message=f"{user.mention} was NOT banned from creating modmail threads.",
                    channel=ctx.channel,
                )

            case ui.ConfirmResponse.CONFIRMED:
                await self.bot.models.ModmailBan(
                    user_id=str(user.id), ban_date=datetime.utcnow()
                ).create()

                return await auxiliary.send_confirm_embed(
                    message=f"{user.mention} was succesfully banned from creating future modmail threads.",
                    channel=ctx.channel,
                )

    @auxiliary.with_typing
    @commands.check(has_modmail_management_role)
    @modmail.command(
        name="unban",
        brief="Unans a user from creating future modmail threads",
        usage="[user-to-unban]",
    )
    async def modmail_unban(self, ctx: commands.Context, user: discord.User):
        """Opens a modmail thread with a person of your choice

        Args:
            ctx (commands.Context): Context of the command execution
            user (discord.User): The user to ban
        """
        ban_entry = await self.bot.models.ModmailBan.query.where(
            self.bot.models.ModmailBan.user_id == str(user.id)
        ).gino.first()

        if not ban_entry:
            return await auxiliary.send_deny_embed(
                message=f"{user.mention} is not currently banned from making modmail threads!",
                channel=ctx.channel,
            )

        await ban_entry.delete()

        return await auxiliary.send_confirm_embed(
            message=f"{user.mention} was succesfully unbanned from creating modmail threads!",
            channel=ctx.channel,
        )
