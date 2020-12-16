from cogs import BasicPlugin
from discord.ext import commands
from utils.helpers import priv_response, tagged_response


def setup(bot):
    bot.add_cog(Corrector(bot))


class Corrector(BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False
    SEARCH_LIMIT = 50

    @commands.command(
        aliases=["c"],
        brief="Corrects a message",
        description="Replaces the most recent text with your text",
        usage="[to_replace] [replacement]",
        help="\nLimitations: max search limit",
    )
    async def correct(self, ctx, to_replace, replacement):
        new_content = None
        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author.bot or message.content.startswith(
                self.bot.config.main.required.command_prefix
            ):
                continue

            if to_replace in message.content:
                new_content = message.content.replace(to_replace, f"**{replacement}**")
                break

        if new_content:
            await tagged_response(
                ctx, f"*Correction:* {new_content} :white_check_mark:"
            )
        else:
            await priv_response(ctx, "I couldn't find any message to correct")
