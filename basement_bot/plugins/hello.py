from discord.ext import commands

@commands.command(name="hello")
async def hello(ctx):
    await ctx.send("Hello to you!")
