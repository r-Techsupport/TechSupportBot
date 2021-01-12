from cogs import BasicPlugin
from discord.ext import commands
from utils.embed import SafeEmbed
from utils.helpers import *


def setup(bot):
    bot.add_cog(Embedder(bot))


class Embedder(BasicPlugin):

    PLUGIN_NAME = "Embedder"
    HAS_CONFIG = False

    @with_typing
    @commands.has_permissions(manage_messages=True)
    @commands.command(name="embed", brief="", description="", usage="")
    async def embed(self, ctx, *args):
        if not ctx.message.attachments:
            await tagged_response(ctx, "Please provide a JSON file for your embed(s)")
            return

        request_body = await get_json_from_attachment(ctx, ctx.message)
        if not request_body:
            return

        embeds = await self.process_request(ctx, request_body)
        if not embeds:
            await tagged_response(
                ctx, "I was unable to generate any embeds from your request"
            )
            return

        sent_messages = []
        delete = False
        for embed in embeds:
            try:
                # in theory this could spam the API?
                sent_message = await ctx.send(embed=embed)
                sent_messages.append(sent_message)
            except Exception:
                delete = True

        if delete:
            if args and args[0] == "keep":
                await priv_response(ctx, "I couldn't generate all of your embeds")
                return

            for message in sent_messages:
                await message.delete()

            await priv_response(
                ctx,
                "I couldn't generate all of your embeds, so I gave you a blank slate. Use `keep` if you want to keep them next time",
            )

    async def process_request(self, ctx, request_body):
        embeds = []
        try:
            for embed_request in request_body.get("embeds", []):
                embeds.append(SafeEmbed.from_dict(embed_request))
        except Exception:
            pass

        return embeds
