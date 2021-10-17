"""Module for custom help commands.
"""

import inspect

import base
import discord
from discord.ext import commands


class Raw(base.BaseCog):
    """Cog object for executing raw Python."""

    ADMIN_ONLY = True

    @commands.command(name="raw")
    async def raw_command(self, ctx):
        if not ctx.message.attachments:
            await self.bot.send_with_mention(ctx, "No Python code found")
            return

        py_code = await ctx.message.attachments[0].read()
        py_code = py_code.decode("UTF-8")

        try:
            await self.aexec(py_code)
        except Exception as exception:
            await self.bot.send_with_mention(ctx, f"Error: ```{exception}```")
            return

        await self.bot.send_with_mention(ctx, self.bot.CONFIRM_YES_EMOJI)

    async def aexec(self, code):
        # Make an async function with the code and `exec` it
        exec(f"async def __ex(self): " + "".join(f"\n {l}" for l in code.split("\n")))

        # Get `__ex` from local variables, call it and return the result
        return await locals()["__ex"](self)
