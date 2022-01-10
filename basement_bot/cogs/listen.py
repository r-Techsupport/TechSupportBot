"""Module for channel listening.
"""

import datetime

import base
import discord
import embeds
from discord.ext import commands


class ListenChannel(commands.Converter):
    """Converter for grabbing a channel via the API.

    This avoids the limitation set by the builtin channel converters.
    """

    async def convert(self, ctx, argument: int):
        """Convert method for the converter.

        parameters:
            ctx (discord.ext.commands.Context): the context object
            argument (int): the channel ID to convert
        """
        channel = await ctx.bot.fetch_channel(argument)
        return channel


class ListenEmbed(embeds.SaneEmbed):
    """Base embed for listen events."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.blurple()
        self.timestamp = datetime.datetime.utcnow()


class MessageEmbed(ListenEmbed):
    """Embed for message events."""

    def __init__(self, *args, **kwargs):
        message = kwargs.pop("message")
        super().__init__(*args, **kwargs)
        self.set_author(name=message.author.name, icon_url=message.author.avatar_url)

        self.description = message.clean_content
        if message.embeds:
            self.description = f"{self.description} ({len(message.embeds)} embed(s))"

        if message.attachments:
            self.add_field(
                name="Attachments", value=" , ".join(a.url for a in message.attachments)
            )

        self.set_footer(text=f"#{message.channel.name} - {message.guild}")


class InfoEmbed(embeds.SaneEmbed):
    """Embed for providing info about listener jobs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.green()


class Listener(base.BaseCog):
    """Cog object for listening to channels."""

    ADMIN_ONLY = True
    MAX_DESTINATIONS = 10

    # pylint: disable=attribute-defined-outside-init
    async def preconfig(self):
        """Preconfigures the listener cog."""
        self.destinations = {}

    @commands.group(description="Executes a listen command")
    async def listen(self, ctx):
        """Command group for listen commands.

        This is a command and should be accessed via Discord.
        """

    @listen.command(
        description="Starts a listening job", usage="[src-channel] [dst-channel]"
    )
    async def start(self, ctx, src: ListenChannel, dst: ListenChannel):
        """Executes a start-listening command.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            src (ListenChannel): the source channel ID
            dst (ListenChannel): the destination channel ID
        """
        if src.id == dst.id:
            await ctx.send_deny_embed("Source and destination channels must differ")
            return

        destinations = self.get_destinations(src)
        if not destinations:
            destinations = {dst}
        elif dst in destinations:
            await ctx.send_deny_embed("That source and destination already exist")
            return
        elif len(destinations) > self.MAX_DESTINATIONS:
            await ctx.send_deny_embed("There are too many destinations for that source")
            return
        else:
            destinations.add(dst)

        self.destinations[src.id] = destinations
        await ctx.send_confirm_embed("Listening registered!")

    @listen.command(
        description="Stops a listening job", usage="[src-channel] [dst-channel]"
    )
    async def stop(self, ctx, src: ListenChannel, dst: ListenChannel):
        """Executes a stop-listening command.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
            src (ListenChannel): the source channel ID
            dst (ListenChannel): the destination channel ID
        """
        if src.id == dst.id:
            await ctx.send_deny_embed("Source and destination channels must differ")
            return

        destinations = self.get_destinations(src)
        if not dst in destinations:
            await ctx.send_deny_embed(
                "That destination is not registered with that source"
            )
            return

        destinations.remove(dst)
        self.destinations[src.id] = destinations
        await ctx.send_confirm_embed("Listening deregistered!")

    # pylint: disable=attribute-defined-outside-init
    @listen.command(
        description="Clears all listener jobs",
    )
    async def clear(self, ctx):
        """Clears all listener registrations.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        if len(self.destinations) == 0:
            await ctx.send_deny_embed("There are currently no registered listeners")
            return

        self.destinations = {}
        await ctx.send_confirm_embed("All listeners deregistered!")

    @listen.command(
        description="Gets listener job registrations",
    )
    async def jobs(self, ctx):
        """Gets listener job info.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        if len(self.destinations) == 0:
            await ctx.send_deny_embed("There are currently no registered listeners")
            return

        embed = InfoEmbed(
            title="Listener Registrations",
        )
        for src, destinations in self.destinations.items():
            src_ch = await self.bot.fetch_channel(src)
            if not src_ch:
                continue

            dst_str = ""
            for dst in destinations:
                dst_str += f"#{dst.name} - {dst.guild.name}\n"
            embed.add_field(
                name=f"Source: #{src_ch.name} - {src_ch.guild.name}", value=dst_str
            )

        await ctx.send(embed=embed)

    def get_destinations(self, src):
        """Helper for getting destinations for a given source channel.

        parameters:
            src (discord.TextChannel): the channel to reference
        """
        return self.destinations.get(src.id, [])

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handles message events and routes them to their destinations.

        parameters:
            message (discord.Message): the message that triggered the event
        """
        if message.author.bot:
            return

        destinations = self.get_destinations(message.channel)
        sent = 0
        for dst in destinations:
            if sent > self.MAX_DESTINATIONS:
                return
            embed = MessageEmbed(message=message)
            await dst.send(embed=embed)
            sent += 1
