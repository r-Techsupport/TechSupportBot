"""Module for the rules extension of the discord bot."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self

import discord
import munch
from discord import app_commands

from core import auxiliary, cogs
from database.schema import Rule

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the Rules plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(Rules(bot=bot))


class Rules(cogs.BaseCog):
    """Class to define the rules for the extension.

    Attributes:
        RULE_ICON_URL (str): The icon to use for the rules
        rule_group (app_commands.Group): The group for the /rule commands
    """

    RULE_ICON_URL: str = (
        "https://www.iconarchive.com/download/i96945/iconsmind/outline/Scale.512.png"
    )

    rule_group: app_commands.Group = app_commands.Group(
        name="rule", description="View and edit server rules", guild_only=True
    )

    @app_commands.checks.has_permissions(administrator=True)
    @rule_group.command(name="edit", description="Edits rules by uploading JSON")
    async def edit_rules(
        self: Self, interaction: discord.Interaction, json_file: discord.Attachment
    ) -> None:
        """Replace the guild's rules with an uploaded JSON file.

        Args:
            interaction (discord.Interaction): The interaction that called this command
            json_file (discord.Attachment): The JSON file containing the new rules
        """
        try:
            uploaded_data = json.loads(await json_file.read())
        except (ValueError, UnicodeDecodeError):
            embed = auxiliary.prepare_deny_embed(
                message="Please upload a valid JSON file"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if (
            not isinstance(uploaded_data, dict)
            or not isinstance(uploaded_data.get("rules"), list)
            or not all(
                isinstance(rule, dict)
                and isinstance(rule.get("name", ""), str)
                and isinstance(rule.get("description", "None"), str)
                for rule in uploaded_data["rules"]
            )
        ):
            embed = auxiliary.prepare_deny_embed(
                message='The JSON must contain a "rules" list of rule objects'
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        uploaded_data["guild_id"] = str(interaction.guild.id)
        await write_new_rules(interaction.guild, munch.munchify(uploaded_data))
        embed = auxiliary.prepare_confirm_embed(message="I've updated to those rules")
        await interaction.response.send_message(embed=embed)

    @rule_group.command(
        name="get",
        description="Gets a rule by number for the current server",
    )
    async def get_rule(
        self: Self, interaction: discord.Interaction, numbers: str
    ) -> None:
        """Gets the list of rules provided by the invoker

        Args:
            interaction (discord.Interaction): The interaction that called this command
            numbers (str): Comma-separated rule numbers to get
        """
        # Splits content string, and adds each item to number list
        # Catches ValueError when no number is specified
        try:
            numbers = sorted({int(number) for number in numbers.split(",")})
        except ValueError:
            embed = auxiliary.prepare_deny_embed("Please specify a rule number!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get the max rule number
        max_rule = await self.get_rule_count(interaction.guild)

        # Ensure that all rules are valid
        if numbers[0] <= 0 or numbers[-1] > max_rule:
            embed = auxiliary.prepare_deny_embed("Invalid rule numbers")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Build an embed that contains all the given rules
        embed = auxiliary.generate_basic_embed(
            title="Server Rules",
            description="",
            color=discord.Color.gold(),
            url=self.RULE_ICON_URL,
        )
        raw_rules = await get_guild_rules(interaction.guild)
        guild_rules = raw_rules.get("rules")
        for rule_number in numbers:
            embed.add_field(
                name=f"Rule {rule_number}: {guild_rules[rule_number - 1].get('name', '')}",
                value=guild_rules[rule_number - 1].get("description", "None"),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @rule_group.command(
        name="all",
        description="Gets all the rules for the current server",
    )
    async def get_all_rules(self: Self, interaction: discord.Interaction) -> None:
        """Prints an embed containing all of the guild rules

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        rules_data = await get_guild_rules(interaction.guild)
        if not rules_data or not rules_data.get("rules"):
            embed = auxiliary.prepare_confirm_embed(
                "There are no rules for this server"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = auxiliary.generate_basic_embed(
            title="Server Rules",
            description="By talking on this server, you agree to the following rules",
            color=discord.Color.gold(),
        )

        for index, rule in enumerate(rules_data.get("rules")):
            embed.add_field(
                name=f"Rule {index + 1}: {rule.get('name', '')}",
                value=rule.get("description", "None"),
                inline=False,
            )

        embed.set_thumbnail(url=self.RULE_ICON_URL)
        embed.color = discord.Color.gold()

        await interaction.response.send_message(embed=embed)

    async def get_rule_count(self: Self, guild: discord.Guild) -> int:
        """Gets the rule count as an integer for the given guild
        This will create rules should it be called without any rules

        Args:
            guild (discord.Guild): The guild to get the count for

        Returns:
            int: The number of rules in the given guild
        """
        rules_data = await get_guild_rules(guild)
        if not rules_data or not rules_data.get("rules"):
            return 0

        return len(rules_data.get("rules"))


async def get_guild_rules(guild: discord.Guild) -> munch.Munch:
    """Gets the munchified rules for a given guild.
    Will create and write to the database if no rules exist

    Args:
        guild (discord.Guild): The guild to get rules for

    Returns:
        munch.Munch: The munchified rules ready to be parsed and shown to the user
    """
    query = await Rule.objects().where(Rule.guild_id == str(guild.id)).first()
    if not query:
        # Handle case where guild doesn't have rules
        rules_data = json.dumps(
            {
                "rules": [
                    {
                        "name": "Anti-Spam",
                        "description": "No spamming! (this is an example rule)",
                    },
                    {
                        "name": "No Harassment",
                        "description": "Keep it friendly! (this is an example rule)",
                    },
                ],
            }
        )
        new_rules = munch.munchify(json.loads(rules_data))
        await write_new_rules(guild=guild, rules=new_rules)
        return munch.munchify(json.loads(rules_data))
    rules_data = json.loads(query.rules)
    # Older inserts stored JSON inside a second JSON string.
    if isinstance(rules_data, str):
        rules_data = json.loads(rules_data)
    return munch.munchify(rules_data)


async def write_new_rules(guild: discord.Guild, rules: munch.Munch) -> None:
    """This converts the munchified rules into a string and writes it to the database

    Args:
        bot (bot.TechSupportBot): The instance of TS to use
        guild (discord.Guild): The guild to write the rules for
        rules (munch.Munch): The rules to convert and write
    """
    query = await Rule.objects().where(Rule.guild_id == str(guild.id)).first()
    if not query:
        # Handle case where guild doesn't have rules
        new_guild_rules = Rule(guild_id=str(guild.id), rules=json.dumps(rules))
        await new_guild_rules.save()
    else:
        query.rules = json.dumps(rules)
        await query.save(columns=[Rule.rules])
