"""Module for the hug plugin
"""

from random import choice

from discord.ext import commands

from cogs import BasicPlugin
from utils.helpers import priv_response, tagged_response


def setup(bot):
    bot.add_cog(Hugger(bot))


class Hugger(BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False

    HUGS_SELECTION = [
        "{user_giving_hug} hugs {user_to_hug} forever and ever and ever",
        "{user_giving_hug} wraps arms around {user_to_hug} and clings forever",
        "{user_giving_hug} hugs {user_to_hug} and gives their hair a sniff",
        "{user_giving_hug} glomps {user_to_hug}",
        "cant stop, wont stop. {user_giving_hug} hugs {user_to_hug} until the sun goes cold",
        "{user_giving_hug} reluctantly hugs {user_to_hug}...",
        "{user_giving_hug} hugs {user_to_hug} into a coma",
        "{user_giving_hug} smothers {user_to_hug} with a loving hug",
        "{user_giving_hug} squeezes {user_to_hug} to death",
    ]

    @commands.command(
        name="hug",
        brief="Hugs mentioned user(s)",
        description="Hugs the user(s) mentioned after the command.",
        usage="[mentioned-users]",
        help="\nLimitations: Ignores plain text, @everyone, or @here.",
    )
    async def hug(self, ctx):
        """Executes the hug command. Returns bot's response

        parameters:
            ctx (Context): the context
        """
        try:
            if not ctx.message.mentions:
                await priv_response(ctx, "You hugging the air?")
                return

            if ctx.author in ctx.message.mentions:
                await priv_response(ctx, "You tried to hug yourself? You got issues.")
                return

            if len(ctx.message.mentions) > 1:
                mentions = [m.mention for m in ctx.message.mentions]
                await ctx.send(
                    choice(hugs).format(
                        user_giving_hug=ctx.author.mention,
                        user_to_hug=", ".join(mentions[:-1]) + ", and " + mentions[-1],
                    )
                )
                return

            await ctx.send(
                choice(self.HUGS_SELECTION).format(
                    user_giving_hug=ctx.author.mention,
                    user_to_hug=ctx.message.mentions[0].mention,
                )
            )

        except:
            await ctx.send(f"I don't know what you're trying to do!")
