from discord import Forbidden
from munch import Munch

from cogs import MatchPlugin
from utils.helpers import *
from utils.logger import get_logger

log = get_logger("Protector")


def setup(bot):
    bot.add_cog(Protector(bot))


class Protector(MatchPlugin):

    PLUGIN_NAME = __name__

    def match(self, ctx, content):
        if ctx.channel.id in self.config.excluded_channels:
            return False

        ctx.actions = Munch()
        ctx.actions.stringAlert = None
        ctx.actions.lengthAlert = None

        for keyString in list(self.config.stringMap.keys()):
            if keyString in content:
                ctx.actions.stringAlert = self.config.stringMap[keyString]
                break

        if len(content) > self.config.length_limit:
            ctx.actions.lengthAlert = True

        return True

    async def response(self, ctx, content):
        admin = await is_admin(ctx, False)
        if admin:
            return

        if ctx.actions.stringAlert:
            await self.handle_string_alert(ctx, content)

        if ctx.actions.lengthAlert:
            await self.handle_length_alert(ctx, content)

    async def handle_string_alert(self, ctx, content):
        if ctx.actions.stringAlert.delete:
            await delete_message_with_reason(
                ctx,
                ctx.message,
                ctx.actions.stringAlert.message,
                ctx.actions.stringAlert.private,
            )
            return

        if ctx.actions.stringAlert.private:
            await priv_response(ctx, ctx.actions.stringAlert.message)
        else:
            await tagged_response(ctx, ctx.actions.stringAlert.message)

    async def handle_length_alert(self, ctx, content):
        await delete_message_with_reason(
            ctx,
            ctx.message,
            f"Message greater than {self.config.length_limit} characters",
        )
