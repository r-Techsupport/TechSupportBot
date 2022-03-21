"""Module for channel listening.
"""

import datetime

import base
import discord
import embeds
import expiringdict
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
            self.description = f"{self.description} (includes embed)"

        if message.attachments:
            self.add_field(
                name="Attachments", value=" ".join(a.url for a in message.attachments)
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
    CACHE_TIME = 60
    COLLECTION_NAME = "listener"

    # pylint: disable=attribute-defined-outside-init
    async def preconfig(self):
        """Preconfigures the listener cog."""
        self.destination_cache = expiringdict.ExpiringDict(
            max_len=1000,
            max_age_seconds=1200,
        )
        if not self.COLLECTION_NAME in await self.bot.mongo.list_collection_names():
            await self.bot.mongo.create_collection(self.COLLECTION_NAME)

    async def get_destinations(self, src):
        """Gets channel object destinations for a given source channel.

        parameters:
            src (discord.TextChannel): the source channel to build for
        """
        destinations = self.destination_cache.get(src.id)

        if not destinations:
            destinations = await self.build_destinations_from_src(src)
            self.destination_cache[src.id] = destinations

        return destinations

    async def build_destinations_from_src(self, src):
        """Builds channel objects for a given src.

        parameters:
            src (discord.TextChannel): the source channel to build for
        """
        destination_data = await self.get_destination_data(src)
        destination_ids = (
            destination_data.get("destinations", []) if destination_data else []
        )
        destinations = await self.build_destinations(destination_ids)
        return destinations

    async def build_destinations(self, destination_ids):
        """Converts destination ID's to their actual channels objects.

        parameters:
            destination_ids ([int]): the destination ID's to reference
        """
        destinations = set()
        for did in destination_ids:
            # the input might be str, make int
            try:
                did = int(did)
            except TypeError:
                continue

            channel = self.bot.get_channel(did)
            if not channel or channel in destinations:
                continue

            destinations.add(channel)

        return destinations

    async def get_destination_data(self, src):
        """Retrieves raw destination data given a source channel.

        parameters:
            src (discord.TextChannel): the source channel to build for
        """
        destination_data = await self.bot.mongo[self.COLLECTION_NAME].find_one(
            {"source_id": {"$eq": str(src.id)}}
        )
        return destination_data

    async def get_all_sources(self):
        """Gets all source data.

        This is kind of expensive, so use lightly.
        """
        source_objects = []
        cursor = self.bot.mongo[self.COLLECTION_NAME].find({})
        for doc in await cursor.to_list(length=50):
            src_ch = self.bot.get_channel(int(doc.get("source_id"), 0))
            if not src_ch:
                continue

            destination_ids = doc.get("destinations")
            if not destination_ids:
                continue

            destinations = await self.build_destinations(destination_ids)
            if not destinations:
                continue

            source_objects.append(
                {"source": src_ch, "destinations": list(destinations)}
            )

        return source_objects

    async def update_destinations(self, src, destination_ids):
        """Updates destinations in Mongo given a src.

        parameters:
            src (discord.TextChannel): the source channel to build for
            destination_ids ([int]): the destination ID's to reference
        """
        as_str = str(src.id)
        new_data = {"source_id": as_str, "destinations": list(set(destination_ids))}
        await self.bot.mongo[self.COLLECTION_NAME].replace_one(
            {"source_id": as_str}, new_data, upsert=True
        )
        try:
            del self.destination_cache[src.id]
        except KeyError:
            pass

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

        destination_data = await self.get_destination_data(src)
        destinations = (
            destination_data.get("destinations", []) if destination_data else []
        )

        if str(dst.id) in destinations:
            await ctx.send_deny_embed("That source and destination already exist")
            return

        if len(destinations) > self.MAX_DESTINATIONS:
            await ctx.send_deny_embed("There are too many destinations for that source")
            return

        destinations.append(str(dst.id))
        await self.update_destinations(src, destinations)

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

        destination_data = await self.get_destination_data(src)
        destinations = (
            destination_data.get("destinations", []) if destination_data else []
        )
        if str(dst.id) not in destinations:
            await ctx.send_deny_embed(
                "That destination is not registered with that source"
            )
            return

        destinations.remove(str(dst.id))
        await self.update_destinations(src, destinations)

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
        await self.bot.mongo[self.COLLECTION_NAME].delete_many({})
        self.destination_cache.clear()

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
        source_objects = await self.get_all_sources()

        if len(source_objects) == 0:
            await ctx.send_deny_embed("There are currently no registered listeners")
            return

        embed = InfoEmbed(
            title="Listener Registrations",
        )
        for source_obj in source_objects:
            src_ch = source_obj.get("source")
            if not src_ch:
                continue

            dst_str = ""
            for dst in source_obj.get("destinations", []):
                dst_str += f"#{dst.name} - {dst.guild.name}\n"
            embed.add_field(
                name=f"Source: #{src_ch.name} - {src_ch.guild.name}",
                value=dst_str,
                inline=False,
            )

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listens to message events.

        parameters:
            message (discord.Message): the message that triggered the event
        """
        if message.author.bot:
            return
        if isinstance(message.channel, discord.DMChannel):
            return
        destinations = await self.get_destinations(message.channel)
        for dst in destinations:
            embed = MessageEmbed(message=message)
            await dst.send(embed=embed)

    @commands.Cog.listener()
    async def on_extension_listener_event(self, payload):
        """Listens for custom extension-based events.

        parameters:
            payload (dict): the data associated with the event
        """
        if not isinstance(getattr(payload, "embed", None), discord.Embed):
            return
        if not isinstance(getattr(payload, "channel", None), discord.TextChannel):
            return

        destinations = await self.get_destinations(payload.channel)
        for dst in destinations:
            await dst.send(embed=payload.embed)
