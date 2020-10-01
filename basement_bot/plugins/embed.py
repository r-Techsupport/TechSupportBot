import ast
import json

import munch
from discord.ext import commands

from cogs import BasicPlugin
from utils.helpers import *


def setup(bot):
    bot.add_cog(Embedder(bot))


class Embedder(BasicPlugin):

    PLUGIN_NAME = "Embedder"
    HAS_CONFIG = False

    @commands.check(is_admin)
    @commands.command(name="embed", brief="", description="", usage="")
    async def embed(self, ctx):
        if not ctx.message.attachments:
            await priv_response(ctx, "Please provide a JSON file for your embed")
            return

        try:
            json_bytes = await ctx.message.attachments[0].read()
            json_str = json_bytes.decode("UTF-8")
            request_body = ast.literal_eval(json_str)
        except Exception as e:
            await priv_response(ctx, f"I couldn't parse your JSON: ```{e}```")
            return

        embed = await self.process_request(ctx, request_body)

        if embed:
            await ctx.send(embed=embed)
        else:
            await priv_response(
                ctx, "I was unable to generate an embed from your request"
            )

    async def process_request(self, ctx, request_body):
        try:
            embed = Embed.from_dict(request_body)
        except Exception:
            embed = None

        return embed
