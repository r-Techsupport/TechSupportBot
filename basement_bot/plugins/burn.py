import random

import cogs
from discord.ext import commands


def setup(bot):
    bot.add_cog(Burn(bot))


class Burn(cogs.BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False
    SEARCH_LIMIT = 50
    PHRASES = [
        "Sick BURN!",
        "Someone is going to need ointment for that BURN!",
        "Fire! Call 911! Someone just got BURNED!",
        "OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOH BURN!",
        "BURN ALERT!",
        "Was that message a hot pan? BECAUSE IT BURNS!",
    ]

    @commands.command(
        brief="Declares a BURN!",
        description="Declares the user's last message as a BURN!",
        usage="@user",
    )
    async def burn(self, ctx):
        if not ctx.message.mentions:
            await self.bot.h.tagged_response(
                ctx, "You must mention a user to declare their message a burn!"
            )
            return

        user_to_match = ctx.message.mentions[0]

        matched_message = None
        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author == user_to_match and not message.content.startswith(
                self.bot.config.main.required.command_prefix
            ):
                matched_message = message
                break

        for emoji in ["🔥", "🚒", "👨‍🚒"]:
            await matched_message.add_reaction(emoji)

        message = random.choice(self.PHRASES)
        await self.bot.h.tagged_response(ctx, f"🔥🔥🔥 {message} 🔥🔥🔥")
