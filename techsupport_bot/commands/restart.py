import discord
from base import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(Restarter(bot=bot))


class Restarter(cogs.BaseCog):
    ADMIN_ONLY = True

    @commands.command(
        name="restart",
        description="Restarts the bot at the container level",
        aliases=["reboot"],
    )
    async def restart(self, ctx: commands.Context) -> None:
        """Restarts the bot.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (commands.Context): the context object for the calling message
        """
        await auxiliary.send_confirm_embed(
            message="Rebooting! Beep boop!", channel=ctx.channel
        )
        # Exit IRC if it's enabled
        irc_config = getattr(self.bot.file_config.api, "irc")
        if irc_config.enable_irc:
            self.bot.irc.exit_irc()

        # Close the bot and let the docker container restart
        await self.bot.close()
