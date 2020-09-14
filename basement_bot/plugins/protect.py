from discord import Forbidden

from cogs import MatchPlugin
from utils.helpers import get_env_value, is_admin, priv_response
from utils.logger import get_logger

log = get_logger("Protector")


def setup(bot):
    bot.add_cog(Protector(bot))


class Protector(MatchPlugin):

    EXCLUDE = [
        int(id)
        for id in get_env_value(
            "PROTECT_EXCLUDE_CHANNELS", "", raise_exception=False
        ).split(",")
        if id
    ]
    LIMIT = int(get_env_value("PROTECT_LENGTH_LIMIT", 500, False))

    def match(self, ctx, content):
        if ctx.channel.id in self.EXCLUDE:
            return False
        if not len(content) > self.LIMIT:
            return False
        return True

    async def response(self, ctx, content):
        admin = await is_admin(ctx, False)
        if admin:
            log.info(f"Allowing spam message by admin {ctx.author.name}")
            return

        try:
            await ctx.message.delete()
            await priv_response(
                ctx,
                f"Your message was deleted because it was greater than {self.LIMIT} characters. Please use a Pastebin (https://pastebin.com)",
            )
        except Forbidden:
            log.warning("Unable to edit spam message due to missing permissions")
