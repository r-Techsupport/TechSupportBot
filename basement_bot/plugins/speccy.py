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

    async def response(self, config, ctx, content, result):
        speccy_id = result[0].split("/")[-1]
        if not speccy_id:
            return

        found_message = await self.bot.send_with_mention(
            ctx, "Speccy link detected - parsing results now..."
        )

        api_response = await self.call_api(speccy_id)
        response_text = await api_response.text()

        response_data = munch.munchify(json.loads(response_text))

        parse_status = response_data.get("Parsed", "Unknown")

        if response_data.get("Status") == "Parsed":
            try:
                embed = await self.generate_embed(ctx, response_data)
                await self.bot.send_with_mention(ctx, embed=embed)
            except Exception:
                await self.bot.send_with_mention(
                    ctx, "I had trouble reading the Speccy results"
                )
            await ctx.message.delete()
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

        mutated_response_data = response_data.copy()
        # we've already added this as the description
        # so filter it out before rendering the data
        del mutated_response_data["Link"]

        # we also don't need these in the render
        del mutated_response_data["Status"]
        del mutated_response_data["ReportDate"]
        del mutated_response_data["CurrentTime"]

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

            embed.add_field(
                name=f"__{section.get('transform', key.upper())}__",
                value=self.generate_multiline_content(content),
                inline=False,
            )

        embed.set_thumbnail(url=self.ICON_URL)

        yikes_score = mutated_response_data.get("Yikes", 0)
        if yikes_score > 3:
            embed.color = discord.Color.red()
        elif yikes_score > 1.5:
            embed.color = discord.Color.yellow()
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

            result += f"**{key}**\n {value}\n"

        return result
