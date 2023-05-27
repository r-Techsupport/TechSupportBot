"""Module for the correct command on the discord bot."""
import base
import discord
import util
from discord.ext import commands


async def setup(bot):
    """Method to add correct to the config."""
    await bot.add_cog(Corrector(bot=bot))


class Corrector(base.BaseCog):
    """Class for the correct command for the discord bot."""

    SEARCH_LIMIT = 50

    def generate_embed(self, content: str) -> discord.Embed:
        embed = discord.Embed(
            title="Correction!", description=f"{content} :white_check_mark:"
        )
        embed.color = discord.Color.green()
        return embed

    async def find_message(
        self, ctx: commands.Context, prefix: str, to_replace: str
    ) -> discord.Message:
        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author.bot or message.content.startswith(prefix):
                continue

            if to_replace in message.content:
                return message

    def prepare_message(
        self, old_content: str, to_replace: str, replacement: str
    ) -> str:
        return old_content.replace(to_replace, f"**{replacement}**")

    async def handle_correct(self, ctx, to_replace: str, replacement: str) -> None:
        prefix = await self.bot.get_prefix(ctx.message)
        message_to_correct = await self.find_message(ctx, prefix, to_replace)
        if not message_to_correct:
            await ctx.send_deny_embed("I couldn't find any message to correct")
            return

        updated_message = self.prepare_message(
            message_to_correct.content, to_replace, replacement
        )
        embed = self.generate_embed(updated_message)
        await ctx.send(embed=embed, targets=[message_to_correct.author])

    @util.with_typing
    @commands.guild_only()
    @commands.command(
        aliases=["c"],
        brief="Corrects a message",
        description="Replaces the most recent text with your text",
        usage="[to_replace] [replacement]",
    )
    async def correct(self, ctx, to_replace: str, replacement: str):
        """Method for the correct command for the discord bot."""
        await self.handle_correct(ctx, to_replace, replacement)
