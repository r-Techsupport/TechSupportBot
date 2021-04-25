"""Module for Discord-ext-IPC routes.
"""

import base
import munch
from discord.ext import ipc


class BotEndpoints(base.BaseCog):
    """Cog object loading IPC routes."""

    @ipc.server.route()
    async def health(self, _):
        """Gets the health status of the bot."""
        return str({"healthy": True})

    @ipc.server.route()
    async def describe(self, _):
        """Gets all relevant bot information."""
        bot_data = munch.Munch()

        bot_data.plugins = self.bot.plugin_api.get_status()
        bot_data.startup_time = str(self.bot.startup_time)
        bot_data.latency = self.bot.latency
        bot_data.description = self.bot.description
        bot_data.guilds = [
            {"id": guild.id, "name": guild.name} for guild in self.bot.guilds
        ]

        return str(bot_data.toJSON())

    @ipc.server.route()
    async def config(self, data):
        """Gets config for the bot or a guild.

        parameters:
            data (object): the data provided by the client request
        """
        if not data.guild_id:
            return str(self.bot.config.toJSON())

        guild = self.bot.get_guild(int(data.guild_id))
        if not guild:
            return str({})

        config = await self.bot.get_context_config(guild=guild)
        # pylint: disable=protected-access
        config._id = str(config._id)

        return str(config.toJSON())
