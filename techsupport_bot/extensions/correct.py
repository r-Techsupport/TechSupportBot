"""Module for the correct command on the discord bot."""
import base
import discord
import util
from discord.ext import commands


def setup(bot):
    """Method to add correct to the config."""
    bot.add_cog(Corrector(bot=bot))


class CorrectEmbed(discord.Embed):
    """Method to create the correct embed for the discord bot."""

    def __init__(self, *args, **kwargs):
        new_content = kwargs.pop("new_content")
        super().__init__(*args, **kwargs)
        self.title = "Correction!"
        self.description = f"{new_content} :white_check_mark:"
        self.color = discord.Color.green()


class Corrector(base.BaseCog):
    """Class for the correct command for the discord bot."""

    SEARCH_LIMIT = 50

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
        new_content = None

        prefix = await self.bot.get_prefix(ctx.message)

        async for message in ctx.channel.history(limit=self.SEARCH_LIMIT):
            if message.author.bot or message.content.startswith(prefix):
                continue

            if to_replace in message.content:
                new_content = message.content.replace(to_replace, f"**{replacement}**")
                target = message.author
                break

        if not new_content:
            await ctx.send_deny_embed("I couldn't find any message to correct")
            return

        embed = CorrectEmbed(new_content=new_content)

        await ctx.send(embed=embed, targets=[target])
