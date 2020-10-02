from discord import Forbidden

from cogs import MatchPlugin
from utils.helpers import get_env_value, is_admin, priv_response
from utils.logger import get_logger

log = get_logger("Protector")


def setup(bot):
    bot.add_cog(Protector(bot))


class Protector(MatchPlugin):

    PLUGIN_NAME = __name__

    def match(self, ctx, content):
        if ctx.channel.id in self.config.excluded_channels:
            return False
        if not len(content) > self.config.length_limit:
            return False
        return True

    async def response(self, ctx, content):
        admin = await is_admin(ctx, False)
        if admin:
            log.info(f"Allowing spam message by admin {ctx.author.name}")
            return

        try:
            message_content = ctx.message.content
            await ctx.message.delete()
            await priv_response(
                ctx,
                f"Your message was deleted because it was greater than {self.config.length_limit} characters. Please use a Pastebin (https://pastebin.com)",
            )
            await priv_response(ctx, f"Original message: ```{message_content}```")
        except Forbidden:
            log.warning("Unable to edit spam message due to missing permissions")
