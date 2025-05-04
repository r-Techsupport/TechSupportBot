"""Module for channel listening."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
import expiringdict
from core import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Listener plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Listener(bot=bot))


class ListenChannel(commands.Converter):
    """Converter for grabbing a channel via the API.

    This avoids the limitation set by the builtin channel converters.
    """

    async def convert(
        self: Self, ctx: commands.Context, argument: int
    ) -> discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread:
        """Convert method for the converter.

        Args:
            ctx (commands.Context): the context object
            argument (int): the channel ID to convert

        Returns:
            discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread:
                The channel object that is associated with the ID
        """
        channel = await ctx.bot.fetch_channel(argument)
        return channel


class Listener(cogs.BaseCog):
    """Cog object for listening to channels."""

    def format_message_in_embed(self: Self, message: discord.Message) -> discord.Embed:
        """Formats a listened message into a pretty embed

        Args:
            message (discord.Message): The raw message to format

        Returns:
            discord.Embed: The stylized embed ready to be sent
        """
        embed = auxiliary.generate_basic_embed(description=message.clean_content)

        embed.timestamp = datetime.datetime.utcnow()
        embed.set_author(
            name=message.author.name, icon_url=message.author.display_avatar.url
        )

        if message.embeds:
            embed.description = f"{embed.description} (includes embed)"

        if message.attachments:
            embed.add_field(
                name="Attachments", value=" ".join(a.url for a in message.attachments)
            )

        embed.set_footer(text=f"#{message.channel.name} - {message.guild}")

        return embed

    async def preconfig(self: Self) -> None:
        """Preconfigures the listener cog."""
        self.destination_cache = expiringdict.ExpiringDict(
            max_len=1000,
            max_age_seconds=1200,
        )

    async def get_destinations(
        self: Self, src: discord.TextChannel
    ) -> list[discord.abc.Messageable]:
        """Gets channel object destinations for a given source channel.

        Args:
            src (discord.TextChannel): the source channel to build for

        Returns:
            list[discord.abc.Messageable]: The list of destinations to send the listened message to
        """
        destinations = self.destination_cache.get(src.id)

        if not destinations:
            destinations = await self.build_destinations_from_src(src)
            self.destination_cache[src.id] = destinations

        return destinations

    async def build_destinations_from_src(
        self: Self, src: discord.TextChannel
    ) -> list[discord.abc.Messageable]:
        """Builds channel objects for a given src.

        Args:
            src (discord.TextChannel): the source channel to build for

        Returns:
            list[discord.abc.Messageable]: The list of destinations to send the listened message to
        """
        destination_data = await self.get_destination_data(src)
        if not destination_data:
            return None
        destinations = await self.build_destinations(destination_data)
        return destinations

    async def build_destinations(
        self: Self, destination_ids: list[int]
    ) -> list[discord.abc.Messageable]:
        """Converts destination ID's to their actual channels objects.

        Args:
            destination_ids (list[int]): the destination ID's to reference

        Returns:
            list[discord.abc.Messageable]: The list of destinations to send the listened message to
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

    async def get_destination_data(self: Self, src: discord.TextChannel) -> list[str]:
        """Retrieves raw destination data given a source channel.

        Args:
            src (discord.TextChannel): the source channel to build for

        Returns:
            list[str]: The list of channel IDs that should have the listened message sent to
        """
        destination_data = await self.bot.models.Listener.query.where(
            self.bot.models.Listener.src_id == str(src.id)
        ).gino.all()
        if not destination_data:
            return None

        return [listener.dst_id for listener in destination_data]

    def build_list_of_sources(
        self: Self, listeners: list[bot.db.model.Listener]
    ) -> list[str]:
        """Builds a list of unique sources from the raw database output

        Args:
            listeners (list[bot.db.model.Listener]): The entire database dumped into a list

        Returns:
            list[str]: The list of unique src channel strings
        """
        src_id_list = [listener.src_id for listener in listeners]
        final_list = list(set(src_id_list))
        return final_list

    async def get_specific_listener(
        self: Self, src: discord.TextChannel, dst: discord.TextChannel
    ) -> bot.db.models.Listener:
        """Gets a database object of the given listener pair

        Args:
            src (discord.TextChannel): The source channel
            dst (discord.TextChannel): The destination channel

        Returns:
            bot.db.models.Listener: The db object, if the listener exists
        """
        listener = (
            await self.bot.models.Listener.query.where(
                self.bot.models.Listener.src_id == str(src.id)
            )
            .where(self.bot.models.Listener.dst_id == str(dst.id))
            .gino.first()
        )
        return listener

    async def get_all_sources(
        self: Self,
    ) -> dict[discord.abc.Messageable, list[discord.abc.Messageable]]:
        """Gets all source data.

        This is kind of expensive, so use lightly.

        Returns:
            dict[discord.abc.Messageable, list[discord.abc.Messageable]]: A dict of all current
                listen jobs from and to every channel
        """
        source_objects = []
        all_listens = await self.bot.models.Listener.query.gino.all()
        source_list = self.build_list_of_sources(all_listens)
        for src in source_list:
            src_ch = self.bot.get_channel(int(src))
            if not src_ch:
                continue

            destination_ids = await self.bot.models.Listener.query.where(
                self.bot.models.Listener.src_id == src
            ).gino.all()
            dst_id_list = [listener.dst_id for listener in destination_ids]
            if not dst_id_list:
                continue

            destinations = await self.build_destinations(dst_id_list)
            if not destinations:
                continue

            source_objects.append(
                {"source": src_ch, "destinations": list(destinations)}
            )

        return source_objects

    async def update_destinations(
        self: Self, src: discord.TextChannel, dst: discord.TextChannel
    ) -> None:
        """Updates destinations in Postgres given a src.

        Args:
            src (discord.TextChannel): the source channel to build for
            dst (discord.TextChannel): the destination channel to build for
        """
        new_listener = self.bot.models.Listener(
            src_id=str(src.id),
            dst_id=str(dst.id),
        )
        await new_listener.create()
        try:
            del self.destination_cache[src.id]
        except KeyError:
            pass

    @commands.check(auxiliary.bot_admin_check_context)
    @commands.group(description="Executes a listen command")
    async def listen(self: Self, ctx: commands.Context) -> None:
        """Command group for listen commands.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
        """

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    @listen.command(
        description="Starts a listening job", usage="[src-channel] [dst-channel]"
    )
    async def start(
        self: Self, ctx: commands.Context, src: ListenChannel, dst: ListenChannel
    ) -> None:
        """Executes a start-listening command.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
            src (ListenChannel): the source channel ID
            dst (ListenChannel): the destination channel ID
        """
        if src.id == dst.id:
            await auxiliary.send_deny_embed(
                message="Source and destination channels must differ",
                channel=ctx.channel,
            )
            return

        listener_object = await self.get_specific_listener(src, dst)
        if listener_object:
            await auxiliary.send_deny_embed(
                message="That source and destination already exist", channel=ctx.channel
            )
            return

        await self.update_destinations(src, dst)

        await auxiliary.send_confirm_embed(
            message="Listening registered!", channel=ctx.channel
        )

    @listen.command(
        description="Stops a listening job", usage="[src-channel] [dst-channel]"
    )
    async def stop(
        self: Self, ctx: commands.Context, src: ListenChannel, dst: ListenChannel
    ) -> None:
        """Executes a stop-listening command.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
            src (ListenChannel): the source channel ID
            dst (ListenChannel): the destination channel ID
        """
        if src.id == dst.id:
            await auxiliary.send_deny_embed(
                message="Source and destination channels must differ",
                channel=ctx.channel,
            )
            return

        listener_object = await self.get_specific_listener(src, dst)
        if not listener_object:
            await auxiliary.send_deny_embed(
                message="That destination is not registered with that source",
                channel=ctx.channel,
            )
            return
        await listener_object.delete()

        await auxiliary.send_confirm_embed(
            message="Listening deregistered!", channel=ctx.channel
        )

    @listen.command(
        description="Clears all listener jobs",
    )
    async def clear(self: Self, ctx: commands.Context) -> None:
        """Clears all listener registrations.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
        """
        all_listens = await self.bot.models.Listener.query.gino.all()
        for listener in all_listens:
            await listener.delete()
        self.destination_cache.clear()

        await auxiliary.send_confirm_embed(
            message="All listeners deregistered!", channel=ctx.channel
        )

    @listen.command(
        description="Gets listener job registrations",
    )
    async def jobs(self: Self, ctx: commands.Context) -> None:
        """Gets listener job info.

        This is a command and should be accessed via Discord.

        Args:
            ctx (commands.Context): the context object for the message
        """
        source_objects = await self.get_all_sources()

        if len(source_objects) == 0:
            await auxiliary.send_deny_embed(
                message="There are currently no registered listeners",
                channel=ctx.channel,
            )
            return

        embed = auxiliary.generate_basic_embed(
            title="Listener Registrations",
            color=discord.Color.green(),
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
    async def on_message(self: Self, message: discord.Message) -> None:
        """Listens to message events.

        Args:
            message (discord.Message): the message that triggered the event
        """
        if message.author.bot:
            return
        if isinstance(message.channel, discord.DMChannel):
            return
        destinations = await self.get_destinations(message.channel)
        if not destinations:
            return
        for dst in destinations:
            embed = self.format_message_in_embed(message=message)
            await dst.send(embed=embed)
