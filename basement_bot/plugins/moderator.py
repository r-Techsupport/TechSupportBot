import datetime

import cogs
import discord
from discord.ext import commands


def setup(bot):
    bot.add_cog(Moderator(bot))


class Moderator(cogs.BasicPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False

    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.group(
        brief="Executes a purge command",
        description="Executes a purge command",
    )
    async def purge(self, ctx):
        pass

    @purge.command(
        name="amount",
        aliases=["x"],
        brief="Purges messages by amount",
        description="Purges the current channel's messages based on amount and author criteria",
        usage="@user @another-user ... [number-to-purge (50 by default)]",
    )
    async def purge_amount(
        self, ctx, targets: commands.Greedy[discord.Member], amount: int = 1
    ):
        # dat constant lookup
        targets = (
            set(user.id for user in ctx.message.mentions)
            if ctx.message.mentions
            else None
        )

        if amount <= 0 or amount > 50:
            amount = 50

        def check(message):
            if not targets or message.author.id in targets:
                return True
            return False

        await ctx.channel.purge(limit=amount, check=check)
        await self.tagged_response(
            ctx,
            f"I finished deleting {amount} messages",
        )

    @purge.command(
        name="duration",
        aliases=["d"],
        brief="Purges messages by duration",
        description="Purges the current channel's messages up to a time based on author criteria",
        usage="@user @another-user ... [duration (minutes)]",
    )
    async def purge_duration(self, ctx, duration_minutes: int):
        timestamp = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=duration_minutes
        )

        await ctx.channel.purge(after=timestamp)
        await self.tagged_response(
            ctx,
            f"I finished deleting messages up to `{timestamp}` UTC",
        )

    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.command(
        name="ban",
        brief="Bans a user",
        description="Bans a user with a given reason",
        usage="@user [reason]",
    )
    async def ban_user(self, ctx, user: discord.Member, *, reason: str = None):
        await ctx.guild.ban(
            user, reason=reason, delete_message_days=self.config.ban_delete_days
        )

        embed = await self.generate_user_modified_embed(user, "ban", reason)

        await self.tagged_response(ctx, embed=embed)

    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.command(
        name="unban",
        brief="Unbans a user",
        description="Unbans a user with a given reason",
        usage="@user [reason]",
    )
    async def unban_user(self, ctx, user: discord.Member, *, reason: str = None):
        await user.unban(reason=reason)

        embed = await self.generate_user_modified_embed(user, "unban", reason)

        await self.tagged_response(ctx, embed=embed)

    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.command(
        name="kick",
        brief="Kicks a user",
        description="Kicks a user with a given reason",
        usage="@user [reason]",
    )
    async def kick_user(self, ctx, user: discord.Member, *, reason: str = None):
        await ctx.guild.kick(user, reason=reason)

        embed = await self.generate_user_modified_embed(user, "kick", reason)

        await self.tagged_response(ctx, embed=embed)

    async def generate_user_modified_embed(self, user, action, reason):
        embed = self.bot.embed_api.Embed(
            title=f"{action.upper()}: {user}", description=f"Reason: {reason}"
        )
        embed.set_thumbnail(url=user.avatar_url)

        return embed
