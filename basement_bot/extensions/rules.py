import datetime
import io
import json

import base
import discord
import util
from discord.ext import commands


def setup(bot):
    bot.add_cog(Rules(bot=bot))


class Rules(base.BaseCog):

    RULE_ICON_URL = "https://cdn.icon-icons.com/icons2/907/PNG/512/balance-scale-of-justice_icon-icons.com_70554.png"
    COLLECTION_NAME = "rules_extension"

    async def preconfig(self):
        if not self.COLLECTION_NAME in await self.bot.mongo.list_collection_names():
            await self.bot.mongo.create_collection(self.COLLECTION_NAME)

    @commands.group(name="rule")
    async def rule_group(self, ctx):
        pass

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @rule_group.command(
        name="edit",
        brief="Edits rules",
        description="Edits rules by uploading JSON",
        usage="|uploaded-json|",
    )
    async def edit_rules(self, ctx):
        collection = self.bot.mongo[self.COLLECTION_NAME]

        uploaded_data = await util.get_json_from_attachments(ctx.message)
        if uploaded_data:
            uploaded_data["guild_id"] = str(ctx.guild.id)
            await collection.replace_one({"guild_id": str(ctx.guild.id)}, uploaded_data)
            await util.send_with_mention(ctx, "I've updated to those rules")
            return

        rules_data = await collection.find_one({"guild_id": {"$eq": str(ctx.guild.id)}})
        if not rules_data:
            rules_data = {
                "guild_id": str(ctx.guild.id),
                "rules": [
                    {"description": "No spamming! (this is an example rule)"},
                    {"description": "Keep it friendly! (this is an example rule)"},
                ],
            }
            await collection.insert_one(rules_data)

        rules_data.pop("_id", None)
        json_file = discord.File(
            io.StringIO(json.dumps(rules_data, indent=4)),
            filename=f"{ctx.guild.id}-rules-{datetime.datetime.utcnow()}.json",
        )

        await util.send_with_mention(
            ctx, content="Re-upload this file to apply new rules", file=json_file
        )

    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @rule_group.command(
        name="get",
        brief="Gets a rule",
        description="Gets a rule by number for the current server",
        usage="[number]",
    )
    async def get_rule(self, ctx, number: int):
        rules_data = await self.bot.mongo[self.extension_name].find_one(
            {"guild_id": {"$eq": str(ctx.guild.id)}}
        )
        if not rules_data or not rules_data.get("rules"):
            await util.send_with_mention(ctx, "There are no rules for this server")
            return

        rules = rules_data.get("rules")

        try:
            rule = rules[number - 1]
        except IndexError:
            rule = None

        if not rule:
            await util.send_with_mention(ctx, "That rule number doesn't exist")
            return

        embed = discord.Embed(
            title=f"Rule {number}", description=rule.get("description", "None")
        )

        embed.set_thumbnail(url=self.RULE_ICON_URL)
        embed.color = discord.Color.gold()

        await util.send_with_mention(ctx, embed=embed)

    @commands.has_permissions(send_messages=True)
    @commands.guild_only()
    @rule_group.command(
        name="all",
        brief="Gets all rules",
        description="Gets all the rules for the current server",
    )
    async def get_all_rules(self, ctx):
        rules_data = await self.bot.mongo[self.extension_name].find_one(
            {"guild_id": {"$eq": str(ctx.guild.id)}}
        )
        if not rules_data or not rules_data.get("rules"):
            await util.send_with_mention(ctx, "There are no rules for this server")
            return

        embed = discord.Embed(
            title="Server Rules",
            description="By talking on this server, you agree to the following rules",
        )

        for index, rule in enumerate(rules_data.get("rules")):
            embed.add_field(
                name=f"Rule {index+1}",
                value=rule.get("description", "None"),
                inline=False,
            )

        embed.set_thumbnail(url=self.RULE_ICON_URL)
        embed.color = discord.Color.gold()

        await ctx.send(embed=embed)
