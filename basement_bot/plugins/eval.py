import asyncio
import datetime
import threading

import cogs
from discord.ext import commands


def setup(bot):
    bot.add_cog(Evaluator(bot))


class Evaluator(cogs.BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False
    THREAD_WAIT_MINUTES = 10
    POLL_WAIT = 1
    # alcohol made me do this
    UNDEFINED_RESULT = "@UNDEFINED@"

    @commands.is_owner()
    @commands.command(
        name="eval",
        brief="Evalulates Python code",
        description="Evaluates a Python expression (bot-owner only)",
        usage="[Python expression]",
    )
    async def evalulate(self, ctx, *, expression: str):
        global result
        global error_
        result = self.UNDEFINED_RESULT
        error_ = None

        def thread_func(expression):
            global result
            global error_
            try:
                result = eval(expression)
            except SyntaxError:
                result = "Syntax Error"
            except Exception as e:
                error_ = e

        thread = threading.Thread(target=thread_func, args=(str(expression),))

        thread.start()

        finish_time = datetime.datetime.now() + datetime.timedelta(
            minutes=self.THREAD_WAIT_MINUTES
        )

        while True:
            if result != self.UNDEFINED_RESULT:
                await self.bot.h.tagged_response(
                    ctx, f"`{result}`" if result is not None else "`None`"
                )
                return

            elif error_ is not None:
                raise RuntimeError(f"Thread finished with error: {error_}")

            elif datetime.datetime.now() > finish_time:
                await self.bot.h.tagged_response(
                    ctx,
                    f"Result not received from eval() after {self.THREAD_WAIT_MINUTES} minutes",
                )
                return

            await asyncio.sleep(self.POLL_WAIT)
