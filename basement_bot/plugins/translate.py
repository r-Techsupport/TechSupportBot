from cogs import HttpPlugin
from decorate import with_typing
from discord.ext import commands


def setup(bot):
    bot.add_cog(Translator(bot))


class Translator(HttpPlugin):

    PLUGIN_NAME = __name__
    HAS_CONFIG = False

    API_URL = "https://api.mymemory.translated.net/get?q={}&langpair={}|{}"

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Translates a message",
        description="Translates a given input message to another language",
        usage='"[message (in quotes)]" [src language code (en)] [dest language code (es)]',
    )
    async def translate(self, ctx, message, src, dest):
        response = await self.http_call(
            "get",
            self.API_URL.format(message, src, dest),
        )
        translated = response.get("responseData", {}).get("translatedText")

        if not translated:
            await self.bot.h.tagged_response(ctx, "I could not translate your message")
            return

        await self.bot.h.tagged_response(ctx, translated)
