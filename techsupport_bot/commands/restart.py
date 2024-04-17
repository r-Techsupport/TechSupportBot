"""
Commands which allows the bot to be restarted
The cog in the file is named:
    Restarter

This file contains 2 commands:
    .restart
    .reboot
"""

from core import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    """Registers the Restarter Cog"""
    await bot.add_cog(Restarter(bot=bot))


class Restarter(cogs.BaseCog):
    """
    The class that holds the reboot command
    """

    @commands.check(auxiliary.bot_admin_check_context)
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

        # Exit modmail if it's enabled
        modmail_cog = ctx.bot.get_cog("Modmail")
        if modmail_cog:
            await modmail_cog.handle_reboot()

        # Ending the event loop
        self.bot.loop.stop()

        # Close the bot and let the docker container restart
        await self.bot.close()
