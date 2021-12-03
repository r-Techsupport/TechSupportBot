import datetime
import json
import re
from time import time

import base
import discord
import munch
import util
from discord.ext import commands


def setup(bot):
    class SpeccyParse(bot.db.Model):
        __tablename__ = "speccyparses"

        speccy_id = bot.db.Column(bot.db.String, primary_key=True)
        blob = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    config = bot.ExtensionConfig()
    config.add(
        key="support_roles",
        datatype="list",
        title="Confirm roles",
        description="List of role names identifying tech support helpers",
        default=[],
    )
    config.add(
        key="support_users",
        datatype="list",
        title="Confirm roles",
        description="List of user ID's identifying tech support helpers",
        default=[],
    )
    config.add(
        key="channels",
        datatype="list",
        title="Tech support channels",
        description="List of channel ID's representing support channels",
        default=[],
    )
    config.add(
        key="idle_time",
        datatype="int",
        title="Auto-support idle time",
        description="The number of minutes required to pass before auto-support is triggered",
        default=60,
    )
    config.add(
        key="auto_support",
        datatype="bool",
        title="Auto tech support toggle",
        description="True if auto tech support should be enabled",
        default=True,
    )

    bot.add_cog(CDIParser(bot=bot, extension_name="techsupport"))
    bot.add_cog(
        SpeccyParser(bot=bot, extension_name="techsupport", models=[SpeccyParse])
    )
    bot.add_cog(HWInfoParser(bot=bot, extension_name="techsupport"))
    bot.add_cog(AutoSupport(bot=bot, extension_name="techsupport"))
    bot.add_extension_config("techsupport", config)


def get_support_roles(ctx, config):
    role_names = config.extensions.techsupport.support_roles.value
    roles = []
    for role_name in role_names:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role:
            roles.append(role)

    return roles


async def is_support_user(ctx):
    config = await ctx.bot.get_context_config(ctx)
    support_roles = get_support_roles(ctx, config)
    if not support_roles and not config.extensions.techsupport.support_users.value:
        raise commands.CommandError("No support roles found")
    if not (
        any(role in ctx.author.roles for role in support_roles)
        or str(ctx.author.id) in config.extensions.techsupport.support_users.value
    ):
        raise commands.MissingAnyRole(support_roles)
    return True


class AutoSupport(base.MatchCog):

    CHANNEL_WAIT_MINUTES = 30
    USER_COOLDOWN_MINUTES = 1440

    async def preconfig(self):
        self.last_support_messages = munch.Munch()
        self.send_records = munch.Munch()
        self.user_records = munch.Munch()

    async def match(self, config, ctx, content):
        # check if message is in a support channel
        if not str(ctx.channel.id) in config.extensions.techsupport.channels.value:
            await self.bot.logger.debug(
                "Channel not in tech support channels - ignoring auto-support"
            )
            return False

        if not config.extensions.techsupport.auto_support.value in [
            True,
            "True",
            "true",
        ]:
            return False

        # check if the user is not a helper
        support_roles = get_support_roles(ctx, config)
        if not support_roles:
            return False

        if (
            any(role in ctx.author.roles for role in support_roles)
            or str(ctx.author.id) in config.extensions.techsupport.support_users.value
        ):
            await self.bot.logger.debug(
                "User is a tech support helper - ignoring auto-support"
            )
            self.last_support_messages[ctx.channel.id] = ctx.message
            return False

        if ctx.message.mentions or ctx.message.reference:
            return False

        now = datetime.datetime.utcnow()

        last_sent_to_user_time = (
            now - self.user_records.get(ctx.author.id)
            if self.user_records.get(ctx.author.id)
            else None
        )

        if (
            last_sent_to_user_time
            and last_sent_to_user_time.seconds / 60.0 < self.USER_COOLDOWN_MINUTES
        ):
            return False

        last_auto_support_time = (
            now - self.send_records.get(ctx.channel.id)
            if self.send_records.get(ctx.channel.id)
            else None
        )

        if (
            last_auto_support_time
            and last_auto_support_time.seconds / 60.0 < self.CHANNEL_WAIT_MINUTES
        ):
            return False

        last_support_message = self.last_support_messages.get(ctx.channel.id)
        if not last_support_message:
            last_support_message = await self.get_last_support_message(
                ctx.channel, support_roles
            )

        last_support_message_created_at = getattr(
            last_support_message, "created_at", None
        )
        last_support_message_time = (
            now - last_support_message_created_at
            if last_support_message_created_at
            else None
        )

        if (
            last_support_message_time is None
            or last_support_message_time.seconds / 60.0
            > config.extensions.techsupport.idle_time.value
        ):
            return True

        return False

    async def get_last_support_message(self, channel, support_roles):
        async for message in channel.history(limit=100):
            target_roles = getattr(message.author, "roles", None)
            if not target_roles:
                continue

            if any(role in target_roles for role in support_roles):
                self.last_support_messages[channel.id] = message
                return message

        return None

    async def response(self, config, ctx, content, result):
        timestamp = datetime.datetime.utcnow()
        self.send_records[ctx.channel.id] = timestamp
        self.user_records[ctx.author.id] = timestamp
        embed = self.generate_embed(ctx)
        await util.send_with_mention(ctx, embed=embed)
        await self.bot.guild_log(
            ctx.guild,
            "logging_channel",
            "info",
            f"Sending tech support auto-helper in #{ctx.channel.name}",
            send=True,
        )

    def generate_embed(self, ctx):
        title = "It looks like there aren't any helper roles around right now"
        description = (
            "I can help by scanning your computer specs and looking for any issues"
        )
        embed = discord.Embed(title=title, description=description)
        embed.set_author(
            name="Tech Support Auto-Support", icon_url=self.bot.user.avatar_url
        )
        embed.add_field(
            name="1. Download Speccy from the following link:",
            value="https://www.ccleaner.com/speccy/download/standard",
            inline=False,
        )
        embed.add_field(
            name="2. Run Speccy & share the URL:",
            value="Click `File` -> `Publish Snapshot` and paste the link in this channel. You should share a URL. Do not share a file or screenshot. *There is nothing sensitive in the published snapshot.*",
            inline=False,
        )
        embed.set_footer(
            text="This is an automated support message. If you need specific help, please wait for a helper or another user to assist you."
        )

        embed.color = discord.Color.green()

        return embed

    @commands.guild_only()
    @commands.check(is_support_user)
    @commands.group(
        brief="Executes an autosupport command",
        description="Executes an autosuport command",
    )
    async def autosupport(self, ctx):
        pass

    @util.with_typing
    @autosupport.command(
        name="state",
        brief="Gets the state of the autosupport cog",
        description="Retrieves the timestamp data associated with the autosupport cog",
        usage="[channel-id (optional)]",
    )
    async def get_state(self, ctx, channel: discord.TextChannel = None):
        if not channel:
            channel = ctx.channel

        config = await self.bot.get_context_config(ctx)

        if not str(channel.id) in config.extensions.techsupport.channels.value:
            await util.send_with_mention(
                ctx, f"#{channel.name} is not configured as a support channel"
            )
            return

        embed = discord.Embed(title=f"Runtime State for #{channel.name}")
        embed.color = discord.Color.blurple()
        embed.set_author(
            name="Tech Support Auto-Support", icon_url=self.bot.user.avatar_url
        )

        support_roles = get_support_roles(ctx, config)
        if not support_roles:
            await util.send_with_mention(ctx, "I couldn't find any support roles")
            return

        last_support_message = self.last_support_messages.get(channel.id)
        if not last_support_message:
            last_support_message = await self.get_last_support_message(
                channel, support_roles
            )

        timestamp = getattr(
            last_support_message, "created_at", "Not found within range"
        )
        embed.add_field(name="Last support message", value=f"{timestamp}", inline=False)

        embed.add_field(
            name="Last sent",
            value=self.send_records.get(channel.id, "Never (since restart)"),
            inline=False,
        )

        embed.set_footer(text="Timezone: UTC")

        count = 0
        for user_record in self.user_records.values():
            now = datetime.datetime.utcnow()
            if (now - user_record).seconds / 60.0 < self.USER_COOLDOWN_MINUTES:
                count += 1

        embed.add_field(name="User cooldowns (total per server)", value=str(count))

        await util.send_with_mention(ctx, embed=embed)


class BaseParser(base.MatchCog):
    async def confirm(self, ctx, message, config):
        roles = get_support_roles(ctx, config)
        confirmed = await self.bot.confirm(
            ctx, message, bypass=roles, delete_after=True
        )
        return confirmed


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

        await self.bot.guild_log(
            ctx.guild,
            "logging_channel",
            "info",
            f"Parsing CDI file from {ctx.author} in #{ctx.channel}",
            send=True,
        )

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
            description=f"{total_drives} total drive(s)",
        )
        embed.set_author(name="CDI Results", icon_url=self.ICON_URL)

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

        embed.color = discord.Color.blurple()

        return embed


class SpeccyParser(BaseParser):

    URL_PATTERN = r"http://speccy.piriform.com/results/[a-zA-Z0-9]+"
    API_URL = "http://134.122.122.133"
    ICON_URL = "https://cdn.icon-icons.com/icons2/195/PNG/256/Speccy_23586.png"
    VALUE_TRIM_LENGTH = 35

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
            ctx, "Speccy link detected! Should I summarize the results?", config
        )
        if not confirmed:
            return

        found_message = await util.send_with_mention(
            ctx, "Parsing Speccy results now..."
        )

        await self.bot.guild_log(
            ctx.guild,
            "logging_channel",
            "info",
            f"Parsing Speccy URL with ID: {speccy_id} from {ctx.author} in #{ctx.channel}",
            send=True,
        )

        cached = False
        response_data = await self.get_cached_parse(ctx, speccy_id)
        if response_data:
            parse_status = response_data.get("Status", "Unknown")
            cached = True
        else:
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
            response_data_copy = response_data.copy()
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
            if not cached:
                await self.cache_parse(ctx, speccy_id, response_data_copy)
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
        layman_info = (
            response_data.get("Layman", "*<Layman info not found>*")
            .strip("\n")
            .replace("\n", "\n - ")
            or "Your Speccy is in good shape!"
        )
        layman_info = f"- {layman_info}"

        return layman_info

    async def generate_embed(self, ctx, response_data):
        response_data = self.prepare_response_fields(response_data)

        yikes_score = response_data.get("Yikes", 0)
        embed = discord.Embed(
            title=f"Yikes Score: `{yikes_score}`",
            description=response_data.Link,
        )
        embed.set_author(name="Speccy Results", icon_url=self.ICON_URL)

        # define the order of rendering and any metadata for each render
        order = [
            {"key": "HardwareSummary", "transform": "HW Summary", "inline": False},
            {"key": "HardwareCheck", "transform": "HW Check"},
            {"key": "SoftwareCheck", "transform": "SW Check"},
            {"key": "OSCheck", "transform": "OS Check", "inline": False},
            {"key": "SecurityCheck", "transform": "Security", "inline": False},
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
                inline=section.get("inline", True),
            )

        embed.add_field(name="__Summary__", value=self.get_layman_info(response_data))

        embed = self.add_yikes_color(embed, response_data)

        return embed

    @staticmethod
    def prepare_response_fields(response_data):
        os_check_data = response_data.get("OSCheck")
        if os_check_data:
            major_os = os_check_data.get("MajorOS")
            minor_os = os_check_data.get("MinorOS")
            os_supported = os_check_data.get("OSSupported")
            os_check_data["OSDetails"] = f"{major_os}: {minor_os} ({os_supported})"
            if major_os is not None:
                del os_check_data["MajorOS"]
            if minor_os is not None:
                del os_check_data["MinorOS"]
            if os_supported is not None:
                del os_check_data["OSSupported"]

        hw_summary_data = response_data.get("HardwareSummary")
        if hw_summary_data:
            motherboard = hw_summary_data.get("Motherboard")
            hw_summary_data["Mobo"] = motherboard
            if motherboard:
                del hw_summary_data["Motherboard"]

        return response_data

    @staticmethod
    def add_yikes_color(embed, response_data):
        yikes_score = response_data.get("Yikes", 0)
        if yikes_score > 3:
            embed.color = discord.Color.red()
        elif yikes_score >= 1.0:
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

            if isinstance(value, int):
                value = str(value)

            if len(value) > self.VALUE_TRIM_LENGTH:
                value = self.trim_value(key, value)

            if self.should_skip_key(key):
                continue
            if self.should_skip_value(value):
                continue

            result += f"**{key}**: {value}\n"

        return result

    def trim_value(self, key, value):
        if key.lower() in ["osdetails"]:
            return value
        if key.lower() == "baddrives":
            return value.replace("\n", ", ")[:-3]

        trimmed_value = value[: self.VALUE_TRIM_LENGTH]
        excess_value = value[self.VALUE_TRIM_LENGTH :]
        padded_value = excess_value.split(" ")[0]
        return trimmed_value + padded_value + "..."

    @staticmethod
    def should_skip_key(key):
        if key.lower() in ["bppc", "dateformat", "datetimeformat", "layman"]:
            return True
        return False

    @staticmethod
    def should_skip_value(value):
        if value is None:
            return True
        if value.lower() in ["false", "", "0"]:
            return True
        return False

    async def cache_parse(self, ctx, speccy_id, response_data):
        parse = self.models.SpeccyParse(
            speccy_id=speccy_id, blob=json.dumps(response_data)
        )
        try:
            await parse.create()
        except Exception as e:
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not cache Speccy parse results",
                send=True,
                exception=e,
            )

    async def get_cached_parse(self, ctx, speccy_id):
        parse = await self.models.SpeccyParse.query.where(
            self.models.SpeccyParse.speccy_id == speccy_id
        ).gino.first()

        if not parse:
            return None

        try:
            response = munch.munchify(json.loads(parse.blob))
        except Exception as e:
            await parse.delete()
            await self.bot.guild_log(
                ctx.guild,
                "logging_channel",
                "error",
                "Could not retrieve valid Speccy results from cache",
                send=True,
                exception=e,
            )
            response = None

        return response


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
            "If this is a HWINFO log file, I can try scanning it. Would you like me to do that?",
            config,
        )
        if not confirmed:
            return

        found_message = await util.send_with_mention(ctx, "Parsing HWInfo logs now...")

        await self.bot.guild_log(
            ctx.guild,
            "logging_channel",
            "info",
            f"Parsing HWInfo logs from {ctx.author} in #{ctx.channel}",
            send=True,
        )

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
        embed = discord.Embed(description="min/average/max")
        embed.set_author(name="HWInfo Summary", icon_url=self.ICON_URL)

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

        embed.color = discord.Color.blurple()

        return embed
