import asyncio
import enum

import aiohttp
import base
import discord
import util
from discord.ext import commands


def setup(bot):
    config = bot.ExtensionConfig()
    config.add(
        key="region",
        datatype="string",
        title="WoW classic region",
        description="The region to use when looking up WoW classic data (us, eu)",
        default="us",
    )
    config.add(
        key="alert_realm",
        datatype="string",
        title="The name of the tracked realm",
        description="The name of the realm to track data for over time (ie, queue status)",
        default=None,
    )
    config.add(
        key="alert_classic",
        datatype="bool",
        title="Classic WoW tracking toggle",
        description="True if the realm alerter should look for WoW classic realms",
        default=False,
    )
    config.add(
        key="alert_channel",
        datatype="str",
        title="Channel for realm alerts",
        description="The ID of the channel to which realm alerts are sent",
        default=None,
    )
    bot.add_extension_config("warcraft", config)
    bot.add_cog(WarcraftCommands(bot=bot))
    bot.add_cog(RealmAlerts(bot=bot, extension_name="warcraft", no_guild=True))


class WarcraftEmbed(discord.Embed):

    ICON_URL = "https://cdn.icon-icons.com/icons2/1381/PNG/512/sakuradungeon_93641.png"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_thumbnail(url=self.ICON_URL)
        self.color = discord.Color.gold()


class Region(enum.Enum):
    US = "us"
    EU = "eu"


class BattleNet(base.LoopCog):

    RETAIL_NAMESPACE = "dynamic-us"
    CLASSIC_NAMESPACE = "dynamic-classic-us"
    OAUTH_URL = "oauth.battle.net/token"

    async def get_oauth_token(self):
        data = {"grant_type": "client_credentials"}
        response = await self.bot.http_call(
            "post",
            f"https://{self.OAUTH_URL}",
            data=data,
            auth=aiohttp.BasicAuth(
                self.bot.file_config.main.api_keys.battlenet_client,
                self.bot.file_config.main.api_keys.battlenet_key,
            ),
        )
        return response.get("access_token")

    def build_base_url(self, region):
        return f"https://{region}.api.blizzard.com/data/wow"

    async def get_realm_id(self, token, region, namespace, realm_name):
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.bot.http_call(
            "get",
            f"{self.build_base_url(region)}/realm/{realm_name.lower()}?namespace={namespace}&locale=en_US",
            headers=headers,
        )
        return response.get("id")

    async def get_realm_data(self, region, namespace, realm_name):
        token = await self.get_oauth_token()
        realm_id = await self.get_realm_id(token, region, namespace, realm_name)
        response = await self.bot.http_call(
            "get",
            f"{self.build_base_url(region)}/connected-realm/{realm_id}?namespace={namespace}&locale=en_US",
            headers={"Authorization": f"Bearer {token}"},
        )
        return response


class WarcraftCommands(BattleNet):
    @commands.group(
        name="wowc",
        brief="Executes a WoW classic command",
        description="Executes a WoW classic command",
    )
    async def wowc(self, ctx):
        pass

    @util.with_typing
    @wowc.command(
        name="realm",
        brief="Gets WoW classic realm info",
        description="Gets WoW classic realm info by name (slug)",
        usage="[realm-name]",
    )
    async def classic_realm(self, ctx, *, realm_name):
        await self.handle_realm_request(ctx, realm_name, classic=True)

    @commands.group(
        name="wow",
        brief="Executes a WoW command",
        description="Executes a WoW command",
    )
    async def wow(self, ctx):
        pass

    @util.with_typing
    @wow.command(
        name="realm",
        brief="Gets WoW realm info",
        description="Gets WoW realm info by name (slug)",
        usage="[realm-name]",
    )
    async def retail_realm(self, ctx, *, realm_name):
        await self.handle_realm_request(ctx, realm_name)

    async def handle_realm_request(self, ctx, realm_name, classic=False):
        namespace = self.RETAIL_NAMESPACE if not classic else self.CLASSIC_NAMESPACE

        config = await self.bot.get_context_config(ctx)
        try:
            region = Region(config.extensions.warcraft.region.value).value
        except ValueError:
            await ctx.send_deny_embed(
                "Invalid BattleNet realm configured - check guild config"
            )
            return

        response = await self.get_realm_data(region, namespace, realm_name)
        status_code = response.get("status_code", "Unknown")
        if response.get("status_code") != 200:
            await ctx.send_deny_embed(
                f"I ran into an error getting realm data (status code = {status_code})"
            )
            return

        game_label = "WoW" if not classic else "WoW Classic"
        embed = WarcraftEmbed(title=f"{game_label} realm info - {realm_name.upper()}")
        embed.add_field(name="ID", value=response.get("id", "Unknown"))
        embed.add_field(
            name="Status", value=response.get("status", {}).get("name", "Unknown")
        )
        embed.add_field(
            name="Queue", value=response.get("has_queue", "Unknown"), inline=False
        )
        embed.add_field(
            name="Population",
            value=response.get("population", {}).get("name", "Unknown"),
        )

        await ctx.send(embed=embed)


class RealmAlerts(BattleNet, base.LoopCog):

    POLL_TIME_SECONDS = 300
    ON_START = True

    async def preconfig(self):
        self.realm_state = {}

    async def wait(self, config, _):
        await self.bot.logger.debug(
            f"Sleeping for {self.POLL_TIME_SECONDS} seconds before resuming Warcraft realm alert polling"
        )
        await asyncio.sleep(self.POLL_TIME_SECONDS)

    async def execute(self, _config, _guild):
        destinations = {}
        found_realms = set()

        # get all configs with only the warcraft projection
        configs = await self.bot.get_all_context_configs(
            {"guild_id": 1, "extensions.warcraft": 1}
        )
        await self.bot.logger.debug("Executing Warcraft realm alert polling")
        for config in configs:
            # check if realm configured
            realm = config.extensions.warcraft.alert_realm.value
            if not realm:
                continue

            if config.guild_id == self.bot.DM_GUILD_ID:
                continue

            # check if bot still in guild
            try:
                guild = self.bot.get_guild(int(config.guild_id))
            except ValueError:
                continue
            if guild is None:
                continue

            # check if channel configured and accessible
            try:
                channel = self.bot.get_channel(
                    int(config.extensions.warcraft.alert_channel.value)
                )
            except ValueError:
                continue
            if channel is None:
                continue

            try:
                region = Region(config.extensions.warcraft.region.value).value
            except ValueError:
                continue

            realm = str(realm).lower()
            pk = f"{realm},{region}"
            if destinations.get(pk) is None:
                destinations[pk] = [channel]
            else:
                destinations[pk].append(channel)

        for pk, channels in destinations.items():
            vals = str(pk).split(",")
            realm_name = vals[0]
            region = vals[1]

            if realm_name in found_realms:
                continue

            namespace = (
                self.RETAIL_NAMESPACE
                if not config.extensions.warcraft.alert_classic
                else self.CLASSIC_NAMESPACE
            )

            # get realm data
            realm_data = await self.get_realm_data(region, namespace, realm_name)
            if not realm_data:
                continue
            found_realms.add(realm_name)

            before_data = self.realm_state.get(realm_name)
            self.realm_state[realm_name] = realm_data
            if not before_data:
                continue

            # create diff from previous polling
            diff = self.build_realm_diff(before_data, realm_data)
            if not diff:
                continue

            await self.send_alert(realm_name, diff, channels)

    def build_realm_diff(self, before_data, after_data):
        # go through every field in the new data
        # if field can't be found in old data, assume no diff due to data corruption
        diff = {}

        def add_field(field, before, after):
            if before != after:
                diff[field] = {"before": before, "after": after}

        add_field("Queue", before_data.get("has_queue"), after_data.get("has_queue"))
        add_field(
            "Status",
            before_data.get("status", {}).get("name"),
            before_data.get("status", {}).get("name"),
        )
        add_field(
            "Population",
            before_data.get("population", {}).get("name"),
            before_data.get("population", {}).get("name"),
        )

        return diff

    async def send_alert(self, realm_name, diff, channels):
        embed = WarcraftEmbed(
            title=f"WoW Classic Realm Alert", description=f"Realm: {realm_name.upper()}"
        )
        for field_name, values in diff.items():
            before = values.get("before")
            after = values.get("after")
            if before is None or after is None:
                continue
            embed.add_field(name=field_name, value=f"Changed from {before} to {after}")

        if len(embed.fields) == 0:
            raise AttributeError("no valid diff embed could be rendered")

        for channel in channels:
            await channel.send(embed=embed)
