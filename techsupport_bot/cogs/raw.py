"""Module for custom help commands.
"""

import base
from discord.ext import commands


class Raw(base.BaseCog):
    """Cog object for executing raw Python."""

    ADMIN_ONLY = True

    @commands.command(
        name="raw", description="Runs raw Python code", usage="|uploaded-python-file|"
    )
    async def raw_command(self, ctx):
        """Executes raw uploaded Python code.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (discord.ext.Context): the context object for the message
        """
        if not ctx.message.attachments:
            await ctx.send_deny_embed("No Python code found")
            return

        py_code = await ctx.message.attachments[0].read()
        py_code = py_code.decode("UTF-8")

        try:
            await self.aexec(py_code)
        except Exception as e:
            await ctx.send_deny_embed(f"Error: ```{e}```")
            return

        await ctx.send_confirm_embed("Code executed!")

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
