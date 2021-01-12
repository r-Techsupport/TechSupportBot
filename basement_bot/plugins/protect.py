from cogs import MatchPlugin
from munch import Munch
from utils.logger import get_logger

log = get_logger("Protector")


def setup(bot):
    bot.add_cog(Protector(bot))


class Protector(MatchPlugin):

    PLUGIN_NAME = __name__

    async def match(self, ctx, content):
        if not ctx.channel.id in self.config.included_channels:
            return False

        ctx.actions = Munch()
        ctx.actions.stringAlert = None
        ctx.actions.lengthAlert = None

        for keyString in list(self.config.stringMap.keys()):
            filterObject = self.config.stringMap[keyString]
            if filterObject.get("sensitive") is None:
                filterObject.sensitive = True
            keyString = keyString if filterObject.sensitive else keyString.lower()
            search = content if filterObject.sensitive else content.lower()
            if keyString in search:
                ctx.actions.stringAlert = self.config.stringMap[keyString]
                break

        if len(content) > self.config.length_limit:
            ctx.actions.lengthAlert = True

        return True

    async def response(self, ctx, content):
        admin = await self.bot.is_bot_admin(ctx)
        if admin:
            return

        if ctx.actions.stringAlert:
            await self.handle_string_alert(ctx, content)

        if ctx.actions.lengthAlert:
            await self.handle_length_alert(ctx, content)

    async def handle_string_alert(self, ctx, _):
        if ctx.actions.stringAlert.delete:
            await self.bot.h.delete_message_with_reason(
                ctx.message,
                ctx.actions.stringAlert.message,
                ctx.actions.stringAlert.private,
            )
            return

        if ctx.actions.stringAlert.private:
            await self.bot.h.priv_response(ctx, ctx.actions.stringAlert.message)
        else:
            await self.bot.h.tagged_response(ctx, ctx.actions.stringAlert.message)

    async def handle_length_alert(self, ctx, _):
        await self.bot.h.delete_message_with_reason(
            ctx.message,
            f"Message greater than {self.config.length_limit} characters",
        )
