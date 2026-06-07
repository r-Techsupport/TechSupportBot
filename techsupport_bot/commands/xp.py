"""Module for the XP extension for the discord bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import configuration
import discord
import expiringdict
from core import auxiliary, cogs
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the XP plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    await bot.add_cog(LevelXP(bot=bot, extension_name="xp"))


class LevelXP(cogs.MatchCog):
    """Class for the LevelXP to make it to discord.

    Attributes:
        xp (app_commands.Group): The group for the /xp commands

    """

    xp: app_commands.Group = app_commands.Group(
        name="xp", description="Command Group for the XP Extension"
    )

    async def preconfig(self: Self) -> None:
        """Sets up the dict"""
        self.ineligible = expiringdict.ExpiringDict(
            max_len=1000,
            max_age_seconds=60,
        )

    @xp.command(
        name="top",
        description="Shows the top 10 XP users in the server",
        extras={
            "usage": "",
            "module": "xp",
        },
    )
    async def top_xp_command(self: Self, interaction: discord.Interaction) -> None:
        """This command will display an embed of the top 10 users with XP

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        await interaction.response.defer()

        top_xp = (
            await self.bot.models.XP.query.order_by(-self.bot.models.XP.xp)
            .where(self.bot.models.XP.xp > 0)
            .where(self.bot.models.XP.guild_id == str(interaction.guild.id))
            .gino.all()
        )[:10]

        if not top_xp:
            embed = auxiliary.prepare_deny_embed(
                "No users currently have XP in this guild"
            )
            await interaction.followup.send(embed=embed)
            return

        embed = discord.Embed(title=f"Top {len(top_xp)} users in this server:")
        description = ""
        index = 1
        for database_entry in top_xp:
            # 1 - DisplayName (username), @XP, xp
            xp_user: discord.Member = await interaction.guild.fetch_member(
                database_entry.user_id
            )
            user_str = f"Unkown user ({database_entry.user_id})"
            xp_role_str = "No role yet"

            if xp_user:
                user_str = f"{xp_user.mention} ({xp_user.name})"
                xp_role = await get_current_XP_role(self.bot, xp_user)
                if xp_role:
                    xp_role_str = xp_role.mention

            description += f"{index} - {user_str}, {xp_role_str}, {database_entry.xp}\n"
            index += 1

        embed.description = description
        embed.color = discord.Color.dark_gold()

        await interaction.followup.send(embed=embed)

    async def match(self: Self, ctx: commands.Context, _: str) -> bool:
        """Checks a given message to determine if XP should be applied

        Args:
            ctx (commands.Context): The context that the original message was sent in

        Returns:
            bool: True if XP should be granted, False if it shouldn't be.
        """
        # Ignore all bot messages
        if ctx.message.author.bot:
            return False

        # Ignore anyone in the ineligible list
        if f"{ctx.guild.id}:{ctx.author.id}" in self.ineligible:
            return False

        # Ignore messages outside of tracked categories
        if ctx.channel.category_id not in configuration.get_config_entry(
            ctx.guild.id, "xp_categories_counted"
        ):
            return False

        # Ignore messages in exlucded channels
        if ctx.channel.id in configuration.get_config_entry(
            ctx.guild.id, "xp_excluded_channels"
        ):
            return False

        # Ignore messages that are too short
        if len(ctx.message.clean_content) < 20:
            return False

        prefix = await self.bot.get_prefix(ctx.message)

        # Ignore messages that are bot commands
        if ctx.message.clean_content.startswith(prefix):
            return False

        # Ignore messages that are factoid calls
        if "factoids" in configuration.get_config_entry(
            ctx.guild.id, "core_enabled_extensions"
        ):
            factoid_prefix = configuration.get_config_entry(
                ctx.guild.id, "factoids_prefix"
            )
            if ctx.message.clean_content.startswith(factoid_prefix):
                return False

        last_message_in_channel = await auxiliary.search_channel_for_message(
            channel=ctx.channel,
            prefix=prefix,
            allow_bot=False,
            skip_messages=[ctx.message.id],
        )
        if last_message_in_channel.author == ctx.author:
            return False

        return True

    async def response(
        self: Self, ctx: commands.Context, content: str, _: bool
    ) -> None:
        """Updates XP for the given user.
        Message has already been validated when you reach this function.

        Args:
            ctx (commands.Context): The context in which the message was sent in
            content (str): The string content of the message
        """
        current_XP = await get_current_XP(self.bot, ctx.author, ctx.guild)
        new_XP = random.randint(10, 20)

        await update_current_XP(self.bot, ctx.author, ctx.guild, (current_XP + new_XP))

        await self.apply_level_ups(ctx.author, (current_XP + new_XP))

        self.ineligible[f"{ctx.guild.id}:{ctx.author.id}"] = True

    async def apply_level_ups(self: Self, user: discord.Member, new_xp: int) -> None:
        """This function will determine if a user leveled up and apply the proper roles

        Args:
            user (discord.Member): The user who just gained XP
            new_xp (int): The new amount of XP the user has
        """
        levels = configuration.get_config_entry(user.guild.id, "xp_level_roles")

        if len(levels) == 0:
            return

        configured_levels = [
            (int(xp_threshold), int(role_id))
            for xp_threshold, role_id in levels.items()
        ]
        configured_role_ids = {role_id for _, role_id in configured_levels}

        # Determine the role id that corresponds to the new XP (target role)
        target_role_id = max(
            ((xp, role_id) for xp, role_id in configured_levels if new_xp >= xp),
            default=(-1, None),
            key=lambda t: t[0],
        )[1]

        # A list of roles IDs related to the level system that the user currently has.
        user_level_roles_ids = [
            role.id for role in user.roles if role.id in configured_role_ids
        ]

        # If the user has only the correct role, do nothing.
        if user_level_roles_ids == [target_role_id]:
            return

        # Otherwise, remove all the roles from user_level_roles and then apply target_role_id
        for role_id in user_level_roles_ids:
            role_object = await user.guild.fetch_role(role_id)
            await user.remove_roles(role_object, reason="Level up")

        if not target_role_id:
            return

        target_role_object = await user.guild.fetch_role(target_role_id)
        await user.add_roles(target_role_object, reason="Level up")


async def get_current_XP(
    bot: object, user: discord.Member, guild: discord.Guild
) -> int:
    """Calls to the database to get the current XP for a user. Returns 0 if no XP

    Args:
        bot (object): The TS bot object to use for the database lookup
        user (discord.Member): The member to look for XP for
        guild (discord.Guild): The guild to fetch the XP from

    Returns:
        int: The current XP for a given user, or 0 if the user has no XP entry
    """
    current_XP = (
        await bot.models.XP.query.where(bot.models.XP.user_id == str(user.id))
        .where(bot.models.XP.guild_id == str(guild.id))
        .gino.first()
    )
    if not current_XP:
        return 0

    return current_XP.xp


async def update_current_XP(
    bot: object, user: discord.Member, guild: discord.Guild, xp: int
) -> None:
    """Calls to the database to get the current XP for a user. Returns 0 if no XP

    Args:
        bot (object): The TS bot object to use for the database lookup
        user (discord.Member): The member to look for XP for
        guild (discord.Guild): The guild to fetch the XP from
        xp (int): The new XP to give the user

    """
    current_XP = (
        await bot.models.XP.query.where(bot.models.XP.user_id == str(user.id))
        .where(bot.models.XP.guild_id == str(guild.id))
        .gino.first()
    )
    if not current_XP:
        current_XP = bot.models.XP(user_id=str(user.id), guild_id=str(guild.id), xp=xp)
        await current_XP.create()
    else:
        await current_XP.update(xp=xp).apply()


async def get_current_XP_role(bot: object, user: discord.Member) -> discord.Role:
    """_summary_

    Args:
        bot (object): The TS bot object to use for fetching information
        user (discord.Member): The member to lookup info on

    Returns:
        discord.Role: The XP role that the user currently has
    """
    levels = configuration.get_config_entry(user.guild.id, "xp_level_roles")

    if len(levels) == 0:
        return None

    configured_levels = [
        (int(xp_threshold), int(role_id)) for xp_threshold, role_id in levels.items()
    ]
    configured_role_ids = {role_id for _, role_id in configured_levels}

    user_level_roles_ids = [
        role.id for role in user.roles if role.id in configured_role_ids
    ]

    if not user_level_roles_ids:
        return None

    role_object = await user.guild.fetch_role(user_level_roles_ids[0])

    return role_object
