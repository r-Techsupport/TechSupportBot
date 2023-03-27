"""
fill this out jim, it should be a summary of the purpose of the file, and the extension
"""
import base
import discord
from discord.ext import commands

def setup(bot):
    """
    Loader function that's called as the bot starts
    """
    bot.add_cog(Whea(bot=bot))


class Whea(base.BaseCog):
    """
    Fill this out jim, it should explain what the extension does
    """

    # Register as a command
    @commands.command(
        name="whea",
        brief="fill this out jim, it should be a brief message that explains what the command does to be displayed in help messages",
        description="fill this out jim, it should be a more detailed description"
        usage="fill this out jim, it should explain the syntax of usage, refer to another file (like translate.py) for formatting"
    )

    async def whea(self, ctx, *, args):
        """
        fill this out jim
        """

        #blah blah blah put your code here
        
        #https://discordpy.readthedocs.io/en/stable/api.html?highlight=embed#discord.Embed
        embed = discord.Embed()
        embed.title = "Hi Jim!"
        embed.add_field(name="new", value="new technology kernel, brought to you by microsoft")
        embed.add_field(name="args", value="`{val}`")
        await ctx.send(embed=embed)
