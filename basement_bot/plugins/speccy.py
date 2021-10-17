import json
import re

import base
import discord
import munch
from discord.ext import commands


def setup(bot):
    bot.process_plugin_setup(cogs=[SpeccyParser])


class SpeccyParser(base.MatchCog):

    URL_PATTERN = r"http://speccy.piriform.com/results/[a-zA-Z0-9]+"
    API_URL = "http://134.122.122.133"
    ICON_URL = "https://cdn.icon-icons.com/icons2/195/PNG/256/Speccy_23586.png"

    async def match(self, config, ctx, content):
        matches = re.findall(self.URL_PATTERN, content, re.MULTILINE)
        return matches

    async def response(self, _, ctx, __, result):
        speccy_id = result[0].split("/")[-1]
        if not speccy_id:
            return

        confirmed = await self.bot.confirm(
            ctx,
            "Speccy link detected. Would you like me to parse the results?",
            delete_after=True,
        )
        if not confirmed:
            return

        found_message = await self.bot.send_with_mention(
            ctx, "Parsing Speccy results now..."
        )

        api_response = await self.call_api(speccy_id)
        response_text = await api_response.text()

        try:
            response_data = munch.munchify(json.loads(response_text))
            parse_status = response_data.get("Status", "Unknown")
        except Exception as e:
            response_data = None
            parse_status = "Error"
            log_channel = await self.bot.get_log_channel_from_guild(
                ctx.guild, "logging_channel"
            )
            await self.bot.logger.error(
                "Could not deserialize Speccy parse response to JSON",
                exception=e,
                channel=log_channel,
            )

        if parse_status == "Parsed":
            try:
                embed = await self.generate_embed(ctx, response_data)
                await self.bot.send_with_mention(ctx, embed=embed)
            except Exception as e:
                await self.bot.send_with_mention(
                    ctx, "I had trouble reading the Speccy results"
                )
                log_channel = await self.bot.get_log_channel_from_guild(
                    ctx.guild, "logging_channel"
                )
                await self.bot.logger.error(
                    "Could not read Speccy results",
                    exception=e,
                    channel=log_channel,
                )
        else:
            await self.bot.send_with_mention(
                ctx,
                f"I was unable to parse that Speccy link (parse status = {parse_status})",
            )

        await found_message.delete()

    async def call_api(self, speccy_id):
        response = await self.bot.http_call(
            "get",
            f"{self.API_URL}/?speccy={speccy_id}&json=true",
            get_raw_response=True,
        )
        return response

    async def generate_embed(self, ctx, response_data):
        embed = discord.Embed(
            title=f"Speccy Results for {ctx.author}", description=response_data.Link
        )

        # define the order of rendering and any metadata for each render
        order = [
            {"key": "Yikes", "transform": "Yikes Score"},
            {"key": "HardwareSummary", "transform": "HW Summary"},
            {"key": "HardwareCheck", "transform": "HW Check"},
            {"key": "OSCheck", "transform": "OS Check"},
            {"key": "SecurityCheck", "transform": "Security"},
            {"key": "SoftwareCheck", "transform": "SW Check"},
        ]

        for section in order:
            key = section.get("key")
            if not key:
                continue

            content = response_data.get(key)
            if not content:
                continue

            try:
                content = self.generate_multiline_content(content)
            except Exception:
                continue

            embed.add_field(
                name=f"__{section.get('transform', key.upper())}__",
                value=content,
                inline=False,
            )

        embed.set_thumbnail(url=self.ICON_URL)

        yikes_score = response_data.get("Yikes", 0)
        if yikes_score > 3:
            embed.color = discord.Color.red()
        elif yikes_score > 0:
            embed.color = discord.Color.gold()
        else:
            embed.color = discord.Color.green()

        return embed

    def generate_multiline_content(self, check_data):
        if not isinstance(check_data, dict):
            return check_data

        result = ""
        for key, value in check_data.items():
            if isinstance(value, list):
                value = ", ".join(value)

            if not value:
                continue

            result += f"**{key}**: {value}\n"

        return result
