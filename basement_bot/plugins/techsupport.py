import asyncio
import json
import re

import base
import discord
import munch
import util


def setup(bot):
    config = bot.PluginConfig()
    config.add(
        key="confirm_roles",
        datatype="list",
        title="Confirm roles",
        description="List of role names able to confirm parses",
        default=[],
    )

    bot.process_plugin_setup(
        cogs=[CDIParser, SpeccyParser, HWInfoParser], config=config
    )


class BaseParser(base.MatchCog):
    async def confirm(self, ctx, message, config):
        roles = self.get_confirm_roles(ctx, config)
        confirmed = await self.bot.confirm(
            ctx, message, bypass=roles, delete_after=True
        )
        return confirmed

    @staticmethod
    def get_confirm_roles(ctx, config):
        role_names = config.plugins.techsupport.confirm_roles.value
        roles = []
        for role_name in role_names:
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if role:
                roles.append(role)

        return roles


class CDIParser(BaseParser):

    API_URL = "http://134.122.122.133"
    ICON_URL = "https://cdn.icon-icons.com/icons2/24/PNG/256/harddiskdrive_hardware_discodur_2522.png"

    async def match(self, config, ctx, content):
        if not ctx.guild:
            return False

        if not ctx.message.attachments:
            return False

        attachment = ctx.message.attachments[0]

        if attachment.filename.lower().endswith(".txt"):
            return attachment.url

        return False

    async def response(self, config, ctx, __, result):
        confirmed = await self.confirm(
            ctx,
            "Is this a Crystal Disk Info (CDI) file?",
            config,
        )
        if not confirmed:
            return

        confirmed = await self.confirm(
            ctx, "Great! Would you like me to parse the results?", config
        )
        if not confirmed:
            return

        found_message = await util.send_with_mention(ctx, "Parsing CDI results now...")

        api_response = await self.call_api(result)

        try:
            response_text = await api_response.text()
            response_data = munch.munchify(json.loads(response_text))
        except Exception as e:
            await util.send_with_mention(
                ctx, "I was unable to convert the parse results to JSON"
            )
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not deserialize CDI parse response to JSON",
                send=True,
                exception=e,
            )
            return await found_message.delete()

        try:
            embed = await self.generate_embed(ctx, response_data)
            await util.send_with_mention(ctx, embed=embed)
        except Exception as e:
            await util.send_with_mention(ctx, "I had trouble reading the CDI logs")
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not read CDI data",
                send=True,
                exception=e,
            )

        return await found_message.delete()

    async def call_api(self, cdi_link):
        response = await util.http_call(
            "get",
            f"{self.API_URL}/?cdi={cdi_link}&json=true",
            get_raw_response=True,
        )
        return response

    async def generate_embed(self, ctx, response_data):
        total_drives = len(response_data.keys())

        embed = discord.Embed(
            title=f"CDI Results for {ctx.author}",
            description=f"{total_drives} total drive(s)",
        )

        for drive_data in response_data.values():
            if not isinstance(drive_data, dict):
                continue

            drive_name = drive_data.get("Model", "Unknown")
            drive_letter = drive_data.get("Drive Letter(s)")
            cdi_health = drive_data.get("CDI Health", "Unknown")
            consult_health = drive_data.get("r/TS Health", "Unknown")
            embed.add_field(
                name=f"`{drive_letter} - {drive_name}`",
                value=f"{cdi_health} | {consult_health}",
                inline=False,
            )

        embed.set_thumbnail(url=self.ICON_URL)
        embed.color = discord.Color.blurple()

        return embed


class SpeccyParser(BaseParser):

    URL_PATTERN = r"http://speccy.piriform.com/results/[a-zA-Z0-9]+"
    API_URL = "http://134.122.122.133"
    ICON_URL = "https://cdn.icon-icons.com/icons2/195/PNG/256/Speccy_23586.png"
    EXPAND_EMOJI = "➕"
    WAIT_FOR_EXPAND_TIMEOUT = 60

    async def match(self, config, ctx, content):
        if not ctx.guild:
            return False

        matches = re.findall(self.URL_PATTERN, content, re.MULTILINE)
        return matches

    async def response(self, config, ctx, __, result):
        speccy_id = result[0].split("/")[-1]
        if not speccy_id:
            return

        confirmed = await self.confirm(
            ctx, "Speccy link detected. Would you like me to parse the results?", config
        )
        if not confirmed:
            return

        found_message = await util.send_with_mention(
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
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not deserialize Speccy parse response to JSON",
                send=True,
                exception=e,
            )

        if parse_status == "Parsed":
            try:
                embed = await self.generate_embed(ctx, response_data)
                await util.send_with_mention(ctx, embed=embed)
            except Exception as e:
                await util.send_with_mention(
                    ctx, "I had trouble reading the Speccy results"
                )
                await self.bot.guild_log(
                    ctx.guild,
                    "logging_channel",
                    "error",
                    "Could not read Speccy results",
                    send=True,
                    exception=e,
                )
        else:
            await util.send_with_mention(
                ctx,
                f"I was unable to parse that Speccy link (parse status = {parse_status})",
            )

        await found_message.delete()

    async def call_api(self, speccy_id):
        response = await util.http_call(
            "get",
            f"{self.API_URL}/?speccy={speccy_id}&json=true",
            get_raw_response=True,
        )
        return response

    @staticmethod
    def get_layman_info(response_data):
        software_check_data = response_data.get("SoftwareCheck")
        layman_info = (
            software_check_data.get("Layman", "*<Layman info not found>*")
            .strip("\n")
            .replace("\n", "\n - ")
            or "Your Speccy is in good shape!"
        )
        layman_info = f"- {layman_info}"

        return layman_info

    async def generate_embed(self, ctx, response_data):
        embed = discord.Embed(
            title=f"Speccy Results for {ctx.author}", description=response_data.Link
        )

        # define the order of rendering and any metadata for each render
        order = [
            {"key": "Yikes", "transform": "Yikes Score"},
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

        embed.add_field(name="__Summary__", value=self.get_layman_info(response_data))

        embed.set_thumbnail(url=self.ICON_URL)

        embed = self.add_yikes_color(embed, response_data)

        return embed

    def add_yikes_color(self, embed, response_data):
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
            if self.should_skip_key(key):
                continue
            if not value or value == "False":
                continue

            if isinstance(value, list):
                value = ", ".join(value)

            result += f"**{key}**: {value}\n"

        return result

    @staticmethod
    def should_skip_key(key):
        if key.lower() in ["bppc", "dateformat", "datetimeformat", "layman"]:
            return True
        return False


class HWInfoParser(BaseParser):

    API_URL = "http://134.122.122.133"
    ICON_URL = (
        "https://cdn.icon-icons.com/icons2/39/PNG/128/hwinfo_info_hardare_6211.png"
    )

    async def match(self, _, ctx, __):
        if not ctx.guild:
            return False

        if not ctx.message.attachments:
            return False

        attachment = ctx.message.attachments[0]

        if attachment.filename.lower().endswith(".csv"):
            return attachment.url

        return False

    async def response(self, config, ctx, __, result):
        confirmed = await self.confirm(
            ctx,
            "If this is a HWINFO log file, I can try parsing it. Would you like me to do that?",
            config,
        )
        if not confirmed:
            return

        found_message = await util.send_with_mention(ctx, "Parsing HWInfo logs now...")

        api_response = await self.call_api(result)

        try:
            response_text = await api_response.text()
            response_data = munch.munchify(json.loads(response_text))
        except Exception as e:
            await util.send_with_mention(
                ctx, "I was unable to convert the parse results to JSON"
            )
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not deserialize HWInfo parse response to JSON",
                send=True,
                exception=e,
            )
            return await found_message.delete()

        try:
            embed = await self.generate_embed(ctx, response_data)
            await util.send_with_mention(ctx, embed=embed)
        except Exception as e:
            await util.send_with_mention(ctx, "I had trouble reading the HWInfo logs")
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not read HWInfo logs",
                send=True,
                exception=e,
            )

        return await found_message.delete()

    async def call_api(self, hwinfo_url):
        response = await util.http_call(
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
            name="__Temperatures of Concern__",
            value=toc_content or "None",
            inline=False,
        )

        embed.set_thumbnail(url=self.ICON_URL)
        embed.color = discord.Color.blurple()

        return embed
