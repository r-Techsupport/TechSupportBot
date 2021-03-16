import base
import decorate
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[Embedder])


class Embedder(base.BaseCog):
    @decorate.with_typing
    @commands.has_permissions(manage_messages=True)
    @commands.command(
        brief="Generates a list of embeds",
        description="Generates a list of embeds defined by an uploaded JSON file (see: https://discord.com/developers/docs/resources/channel#embed-object)",
        usage="|embed-list-json-upload|",
    )
    async def embed(self, ctx, *, keep_option: str = None):
        if not ctx.message.attachments:
            await self.bot.tagged_response(
                ctx, "Please provide a JSON file for your embeds"
            )
            return

        request_body = await self.bot.get_json_from_attachment(ctx.message)
        if not request_body:
            await self.bot.tagged_response(
                ctx, "I couldn't find any data in your upload"
            )
            return

        embeds = await self.process_request(ctx, request_body)
        if not embeds:
            await self.bot.tagged_response(
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
            if keep_option == "keep":
                await ctx.author.send("I couldn't generate all of your embeds")
                return

            for message in sent_messages:
                await message.delete()

            await ctx.author.send(
                "I couldn't generate all of your embeds, so I gave you a blank slate",
            )

    async def process_request(self, ctx, request_body):
        embeds = []
        try:
            for embed_request in request_body.get("embeds", []):
                embeds.append(self.bot.embed_api.Embed.from_dict(embed_request))
        except Exception:
            pass

        return embeds
