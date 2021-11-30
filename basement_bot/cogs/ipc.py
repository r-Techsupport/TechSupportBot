"""Module for IPC endpoints.
"""

import base
import util
from discord.ext import ipc


class IPCEndpoints(base.BaseCog):
    """Cog object for implementing IPC endpoints."""

    MESSAGE_HISTORY_LIMIT = 100

    @ipc.server.route(name="health")
    async def health_endpoint(self, _):
        """Returns a 200 code in the best of circumstances."""
        return util.ipc_response()

    @ipc.server.route(name="describe")
    async def describe_endpoint(self, _):
        """Gets all relevant bot information."""
        return util.ipc_response(payload=self.bot.preserialize_object(self.bot))

    @ipc.server.route(name="get_plugin_status")
    async def plugin_status_endpoint(self, data):
        """IPC endpoint for getting plugin status.

        parameters:
            data (object): the data provided by the client request
        """
        if data.plugin_name:
            payload = self.bot.get_status(data.plugin_name)
            if not payload:
                return util.ipc_response(
                    code=404, error="Plugin not found (in memory or file)"
                )

        else:
            payload = self.bot.get_all_statuses()

        return util.ipc_response(payload=payload)

    @ipc.server.route(name="load_plugin")
    async def load_plugin_endpoint(self, data):
        """IPC endpoint for loading a plugin.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.plugin_name:
            return util.ipc_response(code=400, error="Plugin name not provided")

        response = self.bot.load_plugin(data.plugin_name)
        if not response.status:
            return util.ipc_response(code=500, error=response.message)

        return util.ipc_response()

    @ipc.server.route(name="unload_plugin")
    async def unload_plugin_endpoint(self, data):
        """IPC endpoint for unloading a plugin.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.plugin_name:
            return util.ipc_response(code=400, error="Plugin name not provided")

        response = self.bot.unload_plugin(data.plugin_name)
        if not response.status:
            return util.ipc_response(code=500, error=response.message)

        return util.ipc_response()

    @ipc.server.route(name="echo_user")
    async def echo_user_endpoint(self, data):
        """IPC endpoint for DMing a user.

        parameters:
            data (object): the data provided by the client request
        """
        user = await self.bot.fetch_user(int(data.user_id))
        if not user:
            return util.ipc_response(code=404, error="User not found")

        await user.send(content=data.message)

        return util.ipc_response()

    @ipc.server.route(name="echo_channel")
    async def echo_channel_endpoint(self, data):
        """IPC endpoint for sending to a channel.

        parameters:
            data (object): the data provided by the client request
        """
        channel = self.bot.get_channel(int(data.channel_id))
        if not channel:
            return util.ipc_response(code=404, error="Channel not found")

        await channel.send(content=data.message)

        return util.ipc_response()

    @ipc.server.route(name="get_all_guilds")
    async def get_all_guilds_endpoint(self, _):
        """IPC endpoint for getting all guilds."""
        guilds = [self.bot.preserialize_object(guild) for guild in self.bot.guilds]
        return util.ipc_response(payload={"guilds": guilds})

    @ipc.server.route(name="get_guild")
    async def get_guild_endpoint(self, data):
        """IPC endpoint for getting a single guild.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return util.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return util.ipc_response(code=404, error="Guild not found")

        return util.ipc_response(payload=self.bot.preserialize_object(guild))

    @ipc.server.route(name="get_guild_channels")
    async def get_guild_channels_endpoint(self, data):
        """IPC endpoint for getting detail on guild channels.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return util.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return util.ipc_response(code=404, error="Guild not found")

        channels = []
        for channel in guild.text_channels:
            channels.append(self.bot.preserialize_object(channel))

        print(channels)

        return util.ipc_response(payload={"channels": channels[:-1]})

    @ipc.server.route(name="leave_guild")
    async def leave_guild_endpoint(self, data):
        """IPC endpoint for getting a single guild.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return util.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return util.ipc_response(code=404, error="Guild not found")

        await guild.leave()

        return util.ipc_response()

    @ipc.server.route(name="get_channel_message_history")
    async def get_channel_message_history_endpoint(self, data):
        """IPC endpoint for getting message history for a particular channel.

        parameters:
            data(object): the data provided by the client request
        """
        if not data.channel_id:
            return util.ipc_response(code=400, error="Channel ID not provided")

        # if your bot has a lot of channels
        # this search can sometimes take a while
        try:
            channel = self.bot.get_channel(int(data.channel_id))
        except TypeError:
            channel = None

        if not channel:
            return util.ipc_response(code=404, error="Channel not found")

        try:
            limit = int(data.limit)
            if limit > self.MESSAGE_HISTORY_LIMIT:
                limit = self.MESSAGE_HISTORY_LIMIT
        except TypeError:
            limit = None

        messages = []
        async for message in channel.history(limit=limit):
            message_data = self.bot.preserialize_object(message)
            del message_data["CACHED_SLOTS"]
            del message_data["HANDLERS"]
            messages.append(message_data)

        messages.reverse()

        return util.ipc_response(payload={"history": messages})

    @ipc.server.route(name="get_dm_message_history")
    async def get_dm_message_history_endpoint(self, data):
        """IPC endpoint for getting message history for a particular channel.

        parameters:
            data(object): the data provided by the client request
        """
        if not data.user_id:
            return util.ipc_response(code=400, error="User ID not provided")

        try:
            user = self.bot.get_user(int(data.user_id))
        except TypeError:
            user = None

        if not user:
            return util.ipc_response(code=404, error="User not found")

        try:
            limit = int(data.limit)
            if limit > self.MESSAGE_HISTORY_LIMIT:
                limit = self.MESSAGE_HISTORY_LIMIT
        except TypeError:
            limit = None

        messages = []
        async for message in user.dm_channel.history(limit=limit):
            message_data = self.bot.preserialize_object(message)
            del message_data["CACHED_SLOTS"]
            del message_data["HANDLERS"]
            messages.append(message_data)

        messages.reverse()

        return util.ipc_response(payload={"history": messages})

    @ipc.server.route(name="get_bot_config")
    async def get_bot_config_endpoint(self, _):
        """IPC endpoint for getting bot config."""
        return util.ipc_response(payload=self.bot.config)

    @ipc.server.route(name="get_guild_config")
    async def get_guild_config_endpoint(self, data):
        """IPC endpoint for getting guild config.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return util.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return util.ipc_response(code=404, error="Guild not found")

        config = await self.bot.get_context_config(guild=guild, get_from_cache=True)
        config.pop("_id", None)

        return util.ipc_response(payload=config)

    @ipc.server.route(name="edit_guild_config")
    async def edit_guild_config_endpoint(self, data):
        """IPC endpoint for updating guild config.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return util.ipc_response(code=400, error="Guild ID not provided")

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return util.ipc_response(code=404, error="Guild not found")

        current_config = await self.bot.get_context_config(
            guild=guild, get_from_cache=False
        )

        config = getattr(data, "new_config", None)
        if not config:
            return util.ipc_response(code=400, error="Config not provided")

        if not util.config_schema_matches(config, current_config):
            return util.ipc_response(
                code=400, error="Current config schema doesn't match new config"
            )

        await self.bot.guild_config_collection.replace_one(
            {"guild_id": config.get("guild_id")}, config
        )

        return util.ipc_response()
