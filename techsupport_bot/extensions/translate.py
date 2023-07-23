"""Module for the translate extension for the discord bot."""
import base
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Adding the configuration of the translate extension to the config file."""
    await bot.add_cog(Translator(bot=bot))


class Translator(base.BaseCog):
    """Class to set up the translate extension."""

    HAS_CONFIG = False

    API_URL = "https://api.mymemory.translated.net/get?q={}&langpair={}|{}"

    @util.with_typing
    @commands.command(
        brief="Translates a message",
        description="Translates a given input message to another language",
        usage=(
            '"[message (in quotes)]" [src language code (en)] [dest language code (es)]'
        ),
    )
    async def translate(self, ctx, message, src: str, dest: str):
        """Method to translate a message from one language to another."""
        response = await self.bot.http_call(
            "get",
            self.API_URL.format(message, src, dest),
        )
        translated = response.get("responseData", {}).get("translatedText")

        if not translated:
            await auxiliary.send_deny_embed(
                message="I could not translate your message", channel=ctx.channel
            )
            return

        await auxiliary.send_confirm_embed(message=translated, channel=ctx.channel)
