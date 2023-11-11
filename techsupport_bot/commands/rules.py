"""Module for the rules extension of the discord bot."""
from __future__ import annotations

import datetime
import io
import json
from typing import TYPE_CHECKING

import discord
import munch
from base import auxiliary, cogs
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot):
    """Adding the rules configuration to the config file."""
    await bot.add_cog(Rules(bot=bot))


class RuleEmbed(discord.Embed):
    """Class for setting up the rules embed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = discord.Color.gold()


class Rules(cogs.BaseCog):
    """Class to define the rules for the extension."""

    RULE_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/907/PNG"
        "/512/balance-scale-of-justice_icon-icons.com_70554.png"
    )

    @commands.group(name="rule")
    async def rule_group(self, ctx):
        """Method for the rule group."""

        # Executed if there are no/invalid args supplied
        await auxiliary.extension_help(self, ctx, self.__module__[9:])

    async def get_guild_rules(self, guild: discord.Guild) -> munch.Munch:
        """Gets the munchified rules for a given guild.
        Will create and write to the database if no rules exist

        Args:
            guild (discord.Guild): The guild to get rules for

        Returns:
            munch.Munch: The munchified rules ready to be parsed and shown to the user
        """
        query = await self.bot.models.Rule.query.where(
            self.bot.models.Rule.guild_id == str(guild.id)
        ).gino.first()
        if not query:
            # Handle case where guild doesn't have rules
            rules_data = json.dumps(
                {
                    "rules": [
                        {"description": "No spamming! (this is an example rule)"},
                        {"description": "Keep it friendly! (this is an example rule)"},
                    ],
                }
            )
            new_rules = munch.munchify(json.loads(rules_data))
            await self.write_new_rules(guild=guild, rules=new_rules)
            return munch.munchify(json.loads(rules_data))
        return munch.munchify(json.loads(query.rules))

    async def write_new_rules(self, guild: discord.Guild, rules: munch.Munch) -> None:
        """This converts the munchified rules into a string and writes it to the database

        Args:
            guild (discord.Guild): The guild to write the rules for
            rules (munch.Munch): The rules to convert and write
        """
        query = await self.bot.models.Rule.query.where(
            self.bot.models.Rule.guild_id == str(guild.id)
        ).gino.first()
        if not query:
            # Handle case where guild doesn't have rules
            rules_data = json.dumps(rules)
            new_guild_rules = self.bot.models.Rule(
                guild_id=str(guild.id),
                rules=str(json.dumps(rules_data)),
            )
            await new_guild_rules.create()
        else:
            await query.update(rules=str(json.dumps(rules))).apply()

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @rule_group.command(
        name="edit",
        brief="Edits rules",
        description="Edits rules by uploading JSON",
        usage="|uploaded-json|",
    )
    async def edit_rules(self, ctx: commands.Context):
        """Method to edit the rules that were set up."""

        uploaded_data = await auxiliary.get_json_from_attachments(ctx.message)
        if uploaded_data:
            uploaded_data["guild_id"] = str(ctx.guild.id)
            await self.write_new_rules(ctx.guild, uploaded_data)
            await auxiliary.send_confirm_embed(
                message="I've updated to those rules", channel=ctx.channel
            )
            return

        rules_data = await self.get_guild_rules(ctx.guild)

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
    async def get_rule(self, ctx: commands.Context, content: str):
        """Method to get specified rules from rule number/s specified in content."""
        first = True

        numbers = []
        already_done = []
        errors = []

        # Splits content string, and adds each item to number list
        # Catches ValueError when no number is specified
        try:
            numbers.extend([int(num) for num in content.split(",")])
        except ValueError:
            await auxiliary.send_deny_embed(
                message="Please specify a rule number!", channel=ctx.channel
            )
            return

        for number in numbers:
            if number < 1:
                await auxiliary.send_deny_embed(
                    message="That rule number is invalid", channel=ctx.channel
                )
                return

            rules_data = await self.get_guild_rules(ctx.guild)

            if not rules_data or not rules_data.get("rules"):
                await auxiliary.send_deny_embed(
                    message="There are no rules for this server", channel=ctx.channel
                )
                return
            rules = rules_data.get("rules")
            if number in already_done:
                continue

            try:
                rule = rules[number - 1]
            except IndexError:
                errors.append(number)
                continue

            embed = RuleEmbed(
                title=f"Rule {number}", description=rule.get("description", "None")
            )

            embed.set_thumbnail(url=self.RULE_ICON_URL)
            embed.color = discord.Color.gold()

            # Checks if first embed sent
            if first:
                await ctx.send(
                    embed=embed,
                    content=auxiliary.construct_mention_string(ctx.message.mentions),
                )
                first = False
            else:
                await ctx.send(embed=embed, mention_author=False)

            already_done.append(number)

        for error in errors:
            await auxiliary.send_deny_embed(
                message=f"Rule number {error} doesn't exist", channel=ctx.channel
            )

    @commands.guild_only()
    @rule_group.command(
        name="all",
        brief="Gets all rules",
        description="Gets all the rules for the current server",
    )
    async def get_all_rules(self, ctx: commands.Context):
        """Method to get all the rules that are set up."""
        rules_data = await self.get_guild_rules(ctx.guild)
        if not rules_data or not rules_data.get("rules"):
            await auxiliary.send_confirm_embed(
                message="There are no rules for this server", channel=ctx.channel
            )
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
