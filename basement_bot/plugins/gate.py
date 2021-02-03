import asyncio

import cogs
import discord
from discord.ext import commands


def setup(bot):
    bot.add_cog(ServerGate(bot))


class ServerGate(cogs.MatchPlugin):

    PLUGIN_NAME = __name__

    async def preconfig(self):
        self.channel = self.bot.get_channel(self.config.channel)
        if not self.channel:
            raise RuntimeError("Could not find channel to use as server gate")

    async def match(self, ctx, _):
        if ctx.channel.id != self.channel.id:
            return False
        return True

    async def response(self, ctx, content):
        if content.startswith(self.bot.command_prefix):
            return

        bot_message = None

        if content.lower() == "agree":
            roles = await self.get_roles(ctx)
            if not roles:
                return

            await ctx.author.add_roles(*roles)

            bot_message = await self.bot.h.tagged_response(
                ctx,
                f"{self.config.welcome_message} (this message will delete in {self.config.delete_wait_seconds} seconds)",
            )

        await ctx.message.delete()

        if not bot_message:
            return

        await asyncio.sleep(self.config.delete_wait_seconds)
        await bot_message.delete()

    async def get_roles(self, ctx):
        roles = []
        for role_name in self.config.roles:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if role:
                roles.append(role)

        return roles
