"""Module for the rules extension of the discord bot."""
import datetime
import io
import json

import base
import discord
import util
from discord.ext import commands


def setup(bot):
    """Adding the rules configuration to the config file."""
    bot.add_cog(Rules(bot=bot))


class RuleEmbed(discord.Embed):
    """Class for setting up the rules embed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.gold()


class Rules(base.BaseCog):
    """Class to define the rules for the extension."""

    RULE_ICON_URL = "https://cdn.icon-icons.com/icons2/907/PNG/512/balance-scale-of-justice_icon-icons.com_70554.png"
    COLLECTION_NAME = "rules_extension"

    async def preconfig(self):
        """Method to preconfig the rules."""
        if not self.COLLECTION_NAME in await self.bot.mongo.list_collection_names():
            await self.bot.mongo.create_collection(self.COLLECTION_NAME)

    @commands.group(name="rule")
    async def rule_group(self, ctx):
        """Method for the rule group."""

        # Executed if there are no/invalid args supplied
        await base.extension_help(self, ctx, self.__module__[11:])

        print(f"Rule command called in channel {ctx.channel}")

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @rule_group.command(
        name="edit",
        brief="Edits rules",
        description="Edits rules by uploading JSON",
        usage="|uploaded-json|",
    )
    async def edit_rules(self, ctx):
        """Method to edit the rules that were set up."""
        collection = self.bot.mongo[self.COLLECTION_NAME]

        uploaded_data = await util.get_json_from_attachments(ctx.message)
        if uploaded_data:
            uploaded_data["guild_id"] = str(ctx.guild.id)
            await collection.replace_one({"guild_id": str(ctx.guild.id)}, uploaded_data)
            await ctx.send_confirm_embed("I've updated to those rules")
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

        await ctx.send(content="Re-upload this file to apply new rules", file=json_file)

    @commands.guild_only()
    @rule_group.command(
        name="get",
        brief="Gets a rule",
        description="Gets a rule by number for the current server",
        usage="[number]",
    )
    async def get_rule(self, ctx, content: str):
        """Method to get specified rules from rule number/s specified in content."""
        first = True

        numbers = []

        # Splits content string, and adds each item to number list
        # Catches ValueError when no number is specified
        try:
            numbers.extend([int(num) for num in content.split(",")])
        except ValueError:
            await ctx.send_deny_embed("Please specify a rule number!")
            return

        for number in numbers:
            if number < 1:
                await ctx.send_deny_embed("That rule number is invalid")
                return

            rules_data = await self.bot.mongo[self.COLLECTION_NAME].find_one(
                {"guild_id": {"$eq": str(ctx.guild.id)}}
            )

            if not rules_data or not rules_data.get("rules"):
                await ctx.send_deny_embed("There are no rules for this server")
                return
            rules = rules_data.get("rules")

            try:
                rule = rules[number - 1]
            except IndexError:
                rule = None

            if not rule:
                await ctx.send_deny_embed(f"Rule number {number} doesn't exist")
                return

            embed = RuleEmbed(
                title=f"Rule {number}", description=rule.get("description", "None")
            )

            embed.set_thumbnail(url=self.RULE_ICON_URL)
            embed.color = discord.Color.gold()

            # Checks if first embed sent
            if first:
                await ctx.send(
                    embed=embed, targets=ctx.message.mentions or [ctx.author]
                )
                first = False
            else:
                await ctx.send(embed=embed, mention_author=False)

    @commands.guild_only()
    @rule_group.command(
        name="all",
        brief="Gets all rules",
        description="Gets all the rules for the current server",
    )
    async def get_all_rules(self, ctx):
        """Method to get all the rules that are set up."""
        rules_data = await self.bot.mongo[self.COLLECTION_NAME].find_one(
            {"guild_id": {"$eq": str(ctx.guild.id)}}
        )
        if not rules_data or not rules_data.get("rules"):
            await ctx.send_confirm_embed("There are no rules for this server")
            return

        embed = RuleEmbed(
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

        await ctx.send(embed=embed, mention_author=False)
