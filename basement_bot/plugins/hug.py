"""Module for the hug plugin
"""

from random import choice

from cogs import BasicPlugin
from discord.ext import commands
from helper import with_typing


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
    ICON_URL = (
        "https://cdn.icon-icons.com/icons2/1648/PNG/512/10022huggingface_110042.png"
    )

    @with_typing
    @commands.has_permissions(send_messages=True)
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
        if not ctx.message.mentions:
            await self.bot.h.tagged_response(ctx, "You hugging the air?")
            return

        if ctx.author in ctx.message.mentions:
            await self.bot.h.tagged_response(
                ctx, "You tried to hug yourself? You got issues"
            )
            return

        if len(ctx.message.mentions) > 1:
            mentions = [m.mention for m in ctx.message.mentions]
            await ctx.send(
                choice(self.HUGS_SELECTION).format(
                    user_giving_hug=ctx.author.mention,
                    user_to_hug=", ".join(mentions[:-1]) + ", and " + mentions[-1],
                )
            )
            return

        embed = self.generate_embed(ctx)

        await self.bot.h.tagged_response(ctx, embed=embed)

    def generate_embed(self, ctx):
        hug_text = choice(self.HUGS_SELECTION).format(
            user_giving_hug=ctx.author.mention,
            user_to_hug=ctx.message.mentions[0].mention,
        )

        embed = self.bot.embed_api.Embed()

        embed.add_field(name="You've been hugged!", value=hug_text)

        embed.set_thumbnail(url=self.ICON_URL)

        return embed
