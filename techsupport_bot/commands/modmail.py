"""
Modmail stuff
"""


from datetime import datetime

import discord
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands


# This is not run within the setup hooks because the user *only used for one guild*
class Modmail_bot(discord.Client):
    """The bot used to send and receive DM messages"""

    async def on_message(self, message: discord.Message) -> None:
        """Listens to DMs, forwards them to handle_dm for proper handling

        Args:
            message (discord.Message): Any sent message, gets filtered to only dms
        """
        if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
            await message.add_reaction("✅")
            await handle_dm(message)


# Both of these get assigned in the __init__
Ts_client = None
MODMAIL_CHANNEL_ID = None

intents = discord.Intents.default()
intents.members = True
Modmail_client = Modmail_bot(intents=intents)


async def create_thread(
    channel: discord.TextChannel, user: discord.User, content: str = None
):
    """Creates a thread from a DM message

    Args:
        channel (discord.TextChannel): The forum channel to create the thread in
        message (discord.Message): The original message
    """

    # --> WELCOME MESSAGE <--

    # Formatting the description of the initial message
    description = (
        f"{user.mention} was created {discord.utils.format_dt(user.created_at, 'R')}"
    )

    # Gets past threadss
    past_thread_count = 0
    for thread in channel.threads:
        if int(thread.name.split("|")[-1].strip()) == user.id:
            past_thread_count += 1

    if past_thread_count > 0:
        description += f" and has {past_thread_count} past threads"
    else:
        description += " and has **no** past threads"

    embed = discord.Embed(color=discord.Color.blue(), description=description)

    # If user is a member, do member specific things
    member = channel.guild.get_member(user.id)
    if member:
        description += f", joined at {discord.utils.format_dt(member.joined_at, 'R')}"
        embed.add_field(name="Nickname", value=member.nick)
        roles = []

        for role in sorted(member.roles, key=lambda x: x.position, reverse=True):
            if role.is_default():
                continue
            roles.append(role.mention)

        embed.add_field(name="Roles", value=", ".join(roles))
    else:
        description += ", is not in this server"

    embed.set_author(name=user, icon_url=user.avatar.url)
    embed.set_footer(text=f"User ID: {user.id}")
    embed.timestamp = datetime.utcnow()

    thread = await channel.create_thread(
        name=f"[OPEN] | {user} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {user.id}",
        embed=embed,
    )

    # --> ACTUAL MESSAGE <--
    if content:
        embed = discord.Embed(color=discord.Color.yellow(), description=content)
        embed.set_author(name=user, icon_url=user.avatar.url)
        embed.timestamp = datetime.utcnow()

        await thread[0].send(embed=embed)


async def handle_dm(message: discord.Message) -> None:
    """Sends a registered dm to the appropriate thread

    Args:
        message (discord.Message): The incoming message
    """
    # Finds the channel from TS-es side, so it can create the thread
    modmail_channel = Ts_client.get_channel(MODMAIL_CHANNEL_ID)

    # Tries to find existing threads to send the message to
    try:
        for thread in modmail_channel.threads:
            if (
                thread.name.startswith("[OPEN]")
                and thread.name.split("|")[-1].strip() == message.author.id
            ):
                embed = discord.Embed(
                    color=discord.Color.blue(), description=message.content
                )
                embed.set_author(
                    name=message.author, icon_url=message.author.avatar.url
                )
                embed.set_footer(text=f"Message ID: {message.id}")
                embed.timestamp = datetime.utcnow()

                await thread.send(embed=embed)
                return
    except AttributeError:
        # The channel doesn't have any threads, no need to search
        pass
    await create_thread(modmail_channel, message.author, content=message.content)


async def reply_to_thread(
    content: str,
    author: discord.user,
    thread: discord.Thread,
    anonymous: bool,
):
    """Replies to a modmail message on both the dm side and the ts side

    Args:
        raw_content (str): The message to send
        author (discord.user): The author of the message
        thread (discord.Thread): The thread to reply to
        anonymous (bool): Whether to reply anonymously
    """
    # Removes the command call

    target_member = discord.utils.get(
        thread.guild.members, id=int(thread.name.split("|")[-1].strip())
    )
    # Refetches the user from modmails client so it can reply to it instead of TS
    user = Modmail_client.get_user(target_member.id)

    # - Modmail thread side -
    embed = discord.Embed(color=discord.Color.green(), description=content)
    embed.timestamp = datetime.utcnow()
    embed.set_author(name=author, icon_url=author.avatar.url)
    embed.set_footer(text="Response")

    if anonymous:
        embed.set_footer(text="[Anonymous] Response")

    await thread.send(embed=embed)

    # - User side -
    embed.set_footer(text="Response")

    if anonymous:
        embed.set_author(name="rTechSupport Moderator", icon_url=thread.guild.icon.url)

    await user.send(embed=embed)


# -------------------------------------------------------------------------------------------------


async def setup(bot):
    """Sets the modmail extension up"""
    config = extensionconfig.ExtensionConfig()

    config.add(
        key="aliases",
        datatype="dict",
        title="Aliases for modmail messages",
        description="Custom commands to send message slices",
        default={},
    )

    await bot.add_cog(Modmail(bot=bot))
    bot.add_extension_config("modmail", config)


class Modmail(cogs.BaseCog):
    """The modmail cog class"""

    def __init__(self, bot):
        """Init is used to make variables global so they can be used on the modmail side"""

        # Makes the TS client available to create threads and populate them with info
        # pylint: disable=W0603
        global Ts_client
        Ts_client = bot
        Ts_client.loop.create_task(
            Modmail_client.start(bot.file_config.modmail_config.modmail_auth_token)
        )

        # Sets the modmail channel from config, has to be here otherwise it'd be hardcoded
        # pylint: disable=W0603
        global MODMAIL_CHANNEL_ID
        MODMAIL_CHANNEL_ID = int(bot.file_config.modmail_config.modmail_forum_channel)

        self.global_timeouts = {}
        self.prefix = bot.file_config.modmail_config.modmail_prefix
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Fetches the modmail channel only once ready"""
        await self.bot.wait_until_ready()
        self.modmail_forum = self.bot.get_channel(MODMAIL_CHANNEL_ID)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Processes sent messages matching the prefix sent in modmail threads

        Args:
            message (discord.Message): The sent message
        """
        if (
            not message.content.startswith(self.prefix)
            or not isinstance(message.channel, discord.Thread)
            or message.channel.parent_id != self.modmail_forum.id
            or message.channel.name.startswith("[CLOSED]")
        ):
            return

        # Gets the content without the prefix
        content = message.content.partition(self.prefix)[2]

        # Checks if the message was a command
        match content.split()[0]:
            case "close":
                await message.channel.send(
                    embed=auxiliary.generate_basic_embed(
                        color=discord.Color.red(),
                        title="Thread closed.",
                        description="",
                    )
                )
                await message.channel.edit(
                    name=f"[CLOSED] {message.channel.name[6:]}",
                    archived=True,
                    locked=True,
                )
                return

            case "reply":
                await message.delete()
                await reply_to_thread(
                    " ".join(content.split()[1:]),
                    message.author,
                    message.channel,
                    anonymous=False,
                )
                return

            case "areply":
                await message.delete()
                await reply_to_thread(
                    " ".join(content.split()[1:]),
                    message.author,
                    message.channel,
                    anonymous=True,
                )
                return

        # Checks if it is an alias instead
        config = self.bot.guild_configs[str(self.modmail_forum.guild.id)]
        aliases = config.extensions.modmail.aliases.value

        for alias in aliases:
            if alias != content.split()[0]:
                continue

            await message.delete()
            await reply_to_thread(aliases[alias], message.author, message.channel, True)
            return

    @auxiliary.with_typing
    @commands.command(name="contact", brief="")
    async def contact(self, ctx: commands.Context, user: discord.User):
        """Opens a modmail thread with a person of your choice

        Args:
            ctx (commands.Context): _description_
            user (discord.User): _description_
        """
        modmail_forum = self.bot.get_channel(MODMAIL_CHANNEL_ID)

        for thread in modmail_forum.threads:
            if (
                thread.name.startswith("[OPEN]")
                and int(thread.name.split("|")[-1].strip()) == user.id
            ):
                await auxiliary.send_deny_embed(
                    message=f"User already has an open thread! <#{thread.id}>",
                    channel=ctx.channel,
                )
                return

        await create_thread(modmail_forum, user=user)

        await auxiliary.send_confirm_embed(
            message="Thread succesfully created!", channel=ctx.channel
        )
