import io

import base
import munch


def setup(bot):
    config = bot.PluginConfig()
    config.add(
        key="channels",
        datatype="list",
        title="Protected channels",
        description="The list of channel ID's associated with the channels to protect",
        default=[],
    )
    config.add(
        key="bypass_roles",
        datatype="list",
        title="Bypassed role names",
        description="The list of role names associated with bypassed roles",
        default=[],
    )
    config.add(
        key="bypass_ids",
        datatype="list",
        title="Bypassed member ID's",
        description="The list of member ID's associated with bypassed members",
        default=[],
    )
    config.add(
        key="length_limit",
        datatype="int",
        title="Max length limit",
        description="The max char limit on messages before they trigger an action",
        default=500,
    )
    config.add(
        key="string_map",
        datatype="dict",
        title="Keyword string map",
        description="The mapping of keyword strings to data defining the action to take",
        default={},
    )
    config.add(
        key="alert_channel",
        datatype="int",
        title="Alert channel ID",
        description="The ID of the channel to send protect alerts to",
        default=None,
    )
    config.add(
        key="linx_url",
        datatype="str",
        title="Linx API URL",
        description="The URL to an optional Linx API for pastebinning long messages",
        default=None,
    )

    bot.process_plugin_setup(cogs=[Protector], config=config)


class Protector(base.MatchCog):

    ALERT_ICON_URL = "https://cdn.icon-icons.com/icons2/2063/PNG/512/alert_danger_warning_notification_icon_124692.png"
    CLIPBOARD_ICON_URL = (
        "https://icon-icons.com/icons2/203/PNG/128/diagram-30_24487.png"
    )

    async def match(self, config, ctx, content):
        if not ctx.channel.id in config.plugins.protect.channels.value:
            return False

        admin = await self.bot.is_bot_admin(ctx)
        if admin:
            return False

        role_names = [role.name.lower() for role in getattr(ctx.author, "roles", [])]

        if any(
            role_name.lower() in role_names
            for role_name in config.plugins.protect.bypass_roles.value
        ):
            return False

        if ctx.author.id in config.plugins.protect.bypass_ids.value:
            return False

        # extend alerts here
        ctx.protect_actions = munch.Munch()
        ctx.protect_actions.string_alert = None
        ctx.protect_actions.length_alert = None

        if len(content) > config.plugins.protect.length_limit.value:
            ctx.protect_actions.length_alert = True
            return True

        for keyword, filter_config in config.plugins.protect.string_map.value.items():
            filter_config = munch.munchify(filter_config)
            # make a copy because we might modify it
            search_keyword = keyword
            search_content = content
            if filter_config.get("sensitive"):
                search_keyword = search_keyword.lower()
                search_content = search_content.lower()

            if search_keyword in search_content:
                filter_config["trigger"] = keyword
                ctx.protect_actions.string_alert = filter_config
                return True

    async def response(self, config, ctx, content):
        if ctx.protect_actions.length_alert:
            await self.handle_length_alert(config, ctx, content)
        elif ctx.protect_actions.string_alert:
            await self.handle_string_alert(config, ctx, content)

    async def handle_string_alert(self, config, ctx, content):
        if ctx.protect_actions.string_alert.delete:
            alert_message = f"I deleted your message because: {ctx.protect_actions.string_alert.message}. Check your DM's for the original message"
            await ctx.message.delete()
            await self.send_original_message(ctx, content)
        else:
            alert_message = ctx.protect_actions.string_alert.message

        await self.bot.send_with_mention(ctx, alert_message)
        await self.send_admin_alert(
            config,
            ctx,
            f"Message contained trigger: `{ctx.protect_actions.string_alert.trigger}`",
        )

    async def handle_length_alert(self, config, ctx, content):
        await ctx.message.delete()

        if not config.plugins.protect.linx_url.value:
            await self.default_delete_response(config, ctx)
            return

        linx_embed = await self.create_linx_embed(config, ctx, content)
        if not linx_embed:
            await self.default_delete_response(config, ctx)
            return

        await self.bot.send_with_mention(ctx, embed=linx_embed)

    async def default_delete_response(self, config, ctx):
        await self.bot.send_with_mention(
            ctx,
            f"I deleted your message because it was longer than {config.plugins.protect.length_limit.value} characters. Check your DM's for the original message",
        )
        await ctx.author.send(f"Deleted message: ```{content[:1994]}```")

    async def send_admin_alert(self, config, ctx, message):
        alert_channel = ctx.guild.get_channel(
            int(config.plugins.protect.alert_channel.value)
        )
        if not alert_channel:
            return

        embed = self.bot.embed_api.Embed(
            title="Protect Plugin Alert", description=f"{message}"
        )

        embed.add_field(name="User", value=ctx.author.mention)

        embed.add_field(name="Channel", value=f"#{ctx.channel.name}")

        embed.add_field(name="Message", value=ctx.message.content, inline=False)

        embed.set_thumbnail(url=self.ALERT_ICON_URL)

        await alert_channel.send(embed=embed)

    async def create_linx_embed(self, config, ctx, content):
        if not content:
            return None

        headers = {
            "Linx-Expiry": "1800",
            "Linx-Randomize": "yes",
            "Accept": "application/json",
        }
        file = {"file": io.StringIO(content)}
        response = await self.bot.http_call(
            "post", config.plugins.protect.linx_url.value, headers=headers, data=file
        )

        url = response.get("url")
        if not url:
            return None

        embed = self.bot.embed_api.Embed(
            title=f"Paste by {ctx.author}", description=url
        )

        embed.set_thumbnail(url=self.CLIPBOARD_ICON_URL)

        return embed
