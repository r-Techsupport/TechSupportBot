import asyncio

import cogs
import discord
from discord.ext import commands


def setup(bot):
    bot.add_cog(ServerGate(bot))


class ServerGate(cogs.MatchCog):
    async def preconfig(self):
        self.channels = set()
        for channel_config in self.config.values():
            self.channels.add(channel_config.channel)

    async def match(self, ctx, _):
        if not ctx.channel.id in self.channels:
            return False
        return True

    async def response(self, ctx, content):
        if content.startswith(self.bot.command_prefix):
            return

        guild_config = self.config.get(ctx.guild.id)
        if not guild_config:
            return

        await ctx.message.delete()

        if content.lower() == guild_config.get("passing_text", "agree"):
            roles = await self.get_roles(ctx)
            if not roles:
                return

            await ctx.author.add_roles(*roles)

            welcome_message = guild_config.get(
                "welcome_message", "Welcome to the server!"
            )
            delete_wait = guild_config.get("delete_wait_seconds", 30)

            bot_message = await self.tagged_response(
                ctx,
                f"{welcome_message} (this message will delete in {delete_wait} seconds)",
            )

            await asyncio.sleep(delete_wait)
            await bot_message.delete()

    async def get_roles(self, ctx):
        roles = []
        config_roles = self.config.get(ctx.guild.id, {}).get("roles", [])
        for role_name in config_roles:
            role = discord.utils.get(ctx.guild.roles, name=role_name)

            if role in ctx.author.roles:
                continue

            if role:
                roles.append(role)

        return roles
