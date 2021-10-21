"""Module for custom help commands.
"""

import base
import util
from discord.ext import commands


class Raw(base.BaseCog):
    """Cog object for executing raw Python."""

    ADMIN_ONLY = True

    @commands.command(name="raw")
    async def raw_command(self, ctx):
        """Executes raw uploaded Python code.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        if not ctx.message.attachments:
            await util.send_with_mention(ctx, "No Python code found")
            return

        py_code = await ctx.message.attachments[0].read()
        py_code = py_code.decode("UTF-8")

        try:
            await self.aexec(py_code)
        except Exception as e:
            await util.send_with_mention(ctx, f"Error: ```{e}```")
            return

        await util.send_with_mention(ctx, self.bot.CONFIRM_YES_EMOJI)

    async def aexec(self, code):
        """Uses exec to define a custom async function, and then awaits it.

        parameters:
            code (str): the raw Python code to exec (including async)
        """
        # Make an async function with the code and `exec` it
        # pylint: disable=exec-used
        exec("async def __ex(self): " + "".join(f"\n {l}" for l in code.split("\n")))

        # Get `__ex` from local variables, call it and return the result
        return await locals()["__ex"](self)
