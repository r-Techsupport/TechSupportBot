import discord
from base import auxiliary, cogs
from discord.ext import commands


async def setup(bot):
    await bot.add_cog(Leaver(bot=bot))


class Leaver(cogs.BaseCog):
    ADMIN_ONLY = True

    @commands.command(
        name="leave", description="Leaves a guild by ID", usage="[guild-id]"
    )
    async def leave(self, ctx: commands.Context, *, guild_id: int) -> None:
        """Leaves a guild by ID.

        This is a command and should be accessed via Discord.

        parameters:
            ctx (commands.Context): the context object for the calling message
            guild_id (int): the ID of the guild to leave
        """
        guild = discord.utils.get(self.bot.guilds, id=guild_id)
        if not guild:
            await auxiliary.send_deny_embed(
                message="I don't appear to be in that guild", channel=ctx.channel
            )
            return

        await guild.leave()

        await auxiliary.send_confirm_embed(
            message=f"I have left the guild: {guild.name} ({guild.id})",
            channel=ctx.channel,
        )
