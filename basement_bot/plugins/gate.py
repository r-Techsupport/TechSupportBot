import asyncio

import base
import discord
from discord.ext import commands


def setup(bot):
    config = bot.PluginConfig()
    config.add(
        key="channel",
        datatype="int",
        title="Server Gate Channel ID",
        description="The ID of the channel the gate is in",
        default=None,
    )
    config.add(
        key="roles",
        datatype="list",
        title="Roles to add",
        description="The list of roles to add after user is verified",
        default=[],
    )
    config.add(
        key="welcome_message",
        datatype="str",
        title="Server Gate welcome message",
        description="The message to send to the user after they are verified",
        default="You are now verified! Welcome to the server!",
    )
    config.add(
        key="delete_wait",
        datatype="int",
        title="Welcome message delete time",
        description="The amount of time to wait (in seconds) before deleting the welcome message",
        default=60,
    )
    config.add(
        key="verify_text",
        datatype="str",
        title="Verification text",
        description="The case-insensitive text the user should type to verify themselves",
        default="agree",
    )

    bot.process_plugin_setup(cogs=[ServerGate], config=config)


class ServerGate(base.MatchCog):
    async def match(self, config, ctx, _):
        if not config.plugins.gate.channel.value:
            return False

        return ctx.channel.id == int(config.plugins.gate.channel.value)

    async def response(self, config, ctx, content):
        prefix = await self.bot.get_prefix(ctx.message)

        is_admin = await self.bot.is_admin(ctx)

        if content.startswith(prefix) and is_admin:
            return

        await ctx.message.delete()

        if content.lower() == config.plugins.gate.verify_text.value:
            roles = await self.get_roles(config, ctx)
            if not roles:
                return

            await ctx.author.add_roles(*roles)

            welcome_message = config.plugins.gate.welcome_message.value
            delete_wait = config.plugins.gate.delete_wait.value

            bot_message = await self.bot.tagged_response(
                ctx,
                f"{welcome_message} (this message will delete in {delete_wait} seconds)",
            )

            await asyncio.sleep(delete_wait)
            await bot_message.delete()

    async def get_roles(self, config, ctx):
        roles = []
        for role_name in config.plugins.gate.roles.value:
            role = discord.utils.get(ctx.guild.roles, name=role_name)

            if role in ctx.author.roles:
                continue

            if role:
                roles.append(role)

        return roles
