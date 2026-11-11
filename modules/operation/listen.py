"""Module for channel listening."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Self

import discord
import expiringdict
from discord import app_commands
from discord.ext import commands

from core import auxiliary, cogs
from database.schema import Listener as ListenerModel

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Listener plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Listener(bot=bot))


class ListenChannel(app_commands.Transformer):  # pylint: disable=abstract-method
    """Converter for grabbing a channel via the API.

    This avoids the limitation set by the builtin channel converters.
    """

    async def transform(
        self: Self, interaction: discord.Interaction, argument: str
    ) -> discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread:
        """Resolve a channel ID through the Discord API.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            argument (str): The channel ID to resolve, including channels in other guilds

        Raises:
            AppCommandError: Raised if the channel ID is not a number

        Returns:
            discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread:
                The channel object that is associated with the ID
        """
        try:
            channel_id = int(argument)
        except ValueError as exception:
            raise app_commands.AppCommandError(
                "Please provide a valid channel ID"
            ) from exception
        return await interaction.client.fetch_channel(channel_id)


class Listener(cogs.MatchCog):
    """Cog object for listening to channels.

    Attributes:
        listen_group (app_commands.Group): The group for the /listen commands
    """

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
        destination_data = await ListenerModel.objects().where(
            ListenerModel.src_id == str(src.id)
        )
        if not destination_data:
            return None

        return [listener.dst_id for listener in destination_data]

    def build_list_of_sources(self: Self, listeners: list[ListenerModel]) -> list[str]:
        """Builds a list of unique sources from the raw database output

        Args:
            listeners (list[ListenerModel]): The entire database dumped into a list

        Returns:
            list[str]: The list of unique src channel strings
        """
        src_id_list = [listener.src_id for listener in listeners]
        final_list = list(set(src_id_list))
        return final_list

    async def get_specific_listener(
        self: Self, src: discord.TextChannel, dst: discord.TextChannel
    ) -> ListenerModel | None:
        """Gets a database object of the given listener pair

        Args:
            src (discord.TextChannel): The source channel
            dst (discord.TextChannel): The destination channel

        Returns:
            ListenerModel | None: The db object, or None if the listener does not exist
        """
        listener = (
            await ListenerModel.objects()
            .where(
                ListenerModel.src_id == str(src.id),
                ListenerModel.dst_id == str(dst.id),
            )
            .first()
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
        all_listens = await ListenerModel.objects()
        source_list = self.build_list_of_sources(all_listens)
        for src in source_list:
            src_ch = self.bot.get_channel(int(src))
            if not src_ch:
                continue

            destination_ids = await ListenerModel.objects().where(
                ListenerModel.src_id == src
            )
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
        new_listener = ListenerModel(
            src_id=str(src.id),
            dst_id=str(dst.id),
        )
        await new_listener.save()
        try:
            del self.destination_cache[src.id]
        except KeyError:
            pass

    listen_group: app_commands.Group = app_commands.Group(
        name="listen", description="Manage channel listening jobs", guild_only=True
    )

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @listen_group.command(name="start", description="Starts a listening job")
    async def start(
        self: Self,
        interaction: discord.Interaction,
        src: app_commands.Transform[
            discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread,
            ListenChannel,
        ],
        dst: app_commands.Transform[
            discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread,
            ListenChannel,
        ],
    ) -> None:
        """Executes a start-listening command.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            src (app_commands.Transform[discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread, ListenChannel]): The source channel resolved from its ID
            dst (app_commands.Transform[discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread, ListenChannel]): The destination channel resolved from its ID
        """
        if src.id == dst.id:
            embed = auxiliary.prepare_deny_embed(
                "Source and destination channels must differ"
            )
            await interaction.response.send_message(embed=embed)
            return

        listener_object = await self.get_specific_listener(src, dst)
        if listener_object:
            embed = auxiliary.prepare_deny_embed(
                "That source and destination already exist"
            )
            await interaction.response.send_message(embed=embed)
            return

        await self.update_destinations(src, dst)

        embed = auxiliary.prepare_confirm_embed("Listening registered!")
        await interaction.response.send_message(embed=embed)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @listen_group.command(name="stop", description="Stops a listening job")
    async def stop(
        self: Self,
        interaction: discord.Interaction,
        src: app_commands.Transform[
            discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread,
            ListenChannel,
        ],
        dst: app_commands.Transform[
            discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread,
            ListenChannel,
        ],
    ) -> None:
        """Executes a stop-listening command.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            src (app_commands.Transform[discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread, ListenChannel]): The source channel resolved from its ID
            dst (app_commands.Transform[discord.abc.GuildChannel | discord.abc.PrivateChannel | discord.Thread, ListenChannel]): The destination channel resolved from its ID
        """
        if src.id == dst.id:
            embed = auxiliary.prepare_deny_embed(
                "Source and destination channels must differ"
            )
            await interaction.response.send_message(embed=embed)
            return

        listener_object = await self.get_specific_listener(src, dst)
        if not listener_object:
            embed = auxiliary.prepare_deny_embed(
                "That destination is not registered with that source"
            )
            await interaction.response.send_message(embed=embed)
            return
        await listener_object.remove()
        self.destination_cache.pop(src.id, None)

        embed = auxiliary.prepare_confirm_embed("Listening deregistered!")
        await interaction.response.send_message(embed=embed)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @listen_group.command(
        description="Clears all listener jobs",
    )
    async def clear(self: Self, interaction: discord.Interaction) -> None:
        """Clears all listener registrations.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        all_listens = await ListenerModel.objects()
        for listener in all_listens:
            await listener.remove()
        self.destination_cache.clear()

        embed = auxiliary.prepare_confirm_embed("All listeners deregistered!")
        await interaction.response.send_message(embed=embed)

    @app_commands.check(auxiliary.bot_admin_check_interaction)
    @listen_group.command(
        description="Gets listener job registrations",
    )
    async def jobs(self: Self, interaction: discord.Interaction) -> None:
        """Gets listener job info.

        This is a command and should be accessed via Discord.

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        source_objects = await self.get_all_sources()

        if len(source_objects) == 0:
            embed = auxiliary.prepare_deny_embed(
                "There are currently no registered listeners"
            )
            await interaction.response.send_message(embed=embed)
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

        await interaction.response.send_message(embed=embed)

    async def match(
        self: Self, ctx: commands.Context, _content: str
    ) -> list[discord.abc.Messageable]:
        """Checks if a message sent should be forwarded by listener.

        Args:
            ctx (commands.Context): The context of the incoming message
            _content (str): The message content, unused when matching channels

        Returns:
            list[discord.abc.Messageable]: The destinations, or an empty list if none match
        """
        if ctx.author.bot or ctx.guild is None:
            return []
        return await self.get_destinations(ctx.channel) or []

    async def response(
        self: Self,
        ctx: commands.Context,
        _content: str,
        result: list[discord.abc.Messageable],
    ) -> None:
        """Forward the matched message to its registered destinations.

        Args:
            ctx (commands.Context): The context of the incoming message
            _content (str): The message content, unused when formatting the original message
            result (list[discord.abc.Messageable]): The destinations returned by match
        """
        for destination in result:
            embed = self.format_message_in_embed(message=ctx.message)
            await destination.send(embed=embed)
