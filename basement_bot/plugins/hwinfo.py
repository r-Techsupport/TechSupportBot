import json
import re

import base
import discord
import munch
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[HWInfoParser])


class HWInfoParser(base.MatchCog):

    API_URL = "http://134.122.122.133"
    ICON_URL = (
        "https://cdn.icon-icons.com/icons2/39/PNG/128/hwinfo_info_hardare_6211.png"
    )

    async def match(self, _, ctx, __):
        if not ctx.message.attachments:
            return False

        attachment = ctx.message.attachments[0]

        if attachment.filename.lower().endswith(".csv"):
            return attachment.url

        return False

    async def response(self, _, ctx, __, result):
        confirmed = await self.bot.confirm(
            ctx,
            "If this is a HWINFO log file, I can try parsing it. Would you like me to do that?",
            delete_after=True,
        )
        if not confirmed:
            return

        found_message = await self.bot.send_with_mention(
            ctx, "Parsing HWInfo logs now..."
        )

        api_response = await self.call_api(result)

        try:
            response_text = await api_response.text()
            response_data = munch.munchify(json.loads(response_text))
        except Exception as e:
            await self.bot.send_with_mention(
                ctx, "I was unable to convert the parse results to JSON"
            )
            log_channel = await self.bot.get_log_channel_from_guild(
                ctx.guild, "logging_channel"
            )
            await self.bot.logger.error(
                "Could not deserialize HWInfo parse response to JSON",
                exception=e,
                channel=log_channel,
            )
            return await found_message.delete()

        try:
            embed = await self.generate_embed(ctx, response_data)
            await self.bot.send_with_mention(ctx, embed=embed)
        except Exception as e:
            await self.bot.send_with_mention(
                ctx, "I had trouble reading the HWInfo logs"
            )
            log_channel = await self.bot.get_log_channel_from_guild(
                ctx.guild, "logging_channel"
            )
            await self.bot.logger.error(
                "Could not read HWInfo logs",
                exception=e,
                channel=log_channel,
            )

        return await found_message.delete()

    async def call_api(self, hwinfo_url):
        response = await self.bot.http_call(
            "get",
            f"{self.API_URL}/?hwinfo={hwinfo_url}&json=true",
            get_raw_response=True,
        )
        return response

    async def generate_embed(self, ctx, response_data):
        embed = discord.Embed(
            title=f"HWInfo Summary for {ctx.author}", description="min/average/max"
        )

        summary = ""
        for key, value in response_data.items():
            if key == "ToC":
                continue
            summary += f"**{key.upper()}**: {value}\n"

        embed.add_field(name="__Summary__", value=summary)

        toc_content = ""
        for key, value in response_data.get("ToC", {}).items():
            toc_content += f"**{key.upper()}**: {value}\n"

        embed.add_field(
            name="__Temperatures of Concern__", value=toc_content, inline=False
        )

        embed.set_thumbnail(url=self.ICON_URL)

        return embed
