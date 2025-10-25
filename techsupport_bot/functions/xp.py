"""Module for the XP extension for the discord bot."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Self

import discord
import expiringdict
import munch
from core import auxiliary, cogs, extensionconfig
from discord.ext import commands

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Loading the XP plugin into the bot

    Args:
        bot (bot.TechSupportBot): The bot object to register the cogs to
    """
    config = extensionconfig.ExtensionConfig()
    config.add(
        key="categories_counted",
        datatype="list",
        title="List of category IDs to count for XP",
        description="List of category IDs to count for XP",
        default=[],
    )
    config.add(
        key="level_roles",
        datatype="dict",
        title="Dict of levels in XP:Role ID.",
        description="Dict of levels in XP:Role ID",
        default={},
    )

    await bot.add_cog(LevelXP(bot=bot, extension_name="xp"))
    bot.add_extension_config("xp", config)


class LevelXP(cogs.MatchCog):
    """Class for the LevelXP to make it to discord."""

    async def preconfig(self: Self) -> None:
        """Sets up the dict"""
        self.ineligible = expiringdict.ExpiringDict(
            max_len=1000,
            max_age_seconds=60,
        )

    async def match(
        self: Self, config: munch.Munch, ctx: commands.Context, _: str
    ) -> bool:
        """Checks a given message to determine if XP should be applied

        Args:
            config (munch.Munch): The guild config for the running bot
            ctx (commands.Context): The context that the original message was sent in

        Returns:
            bool: True if XP should be granted, False if it shouldn't be.
        """
        # Ignore all bot messages
        if ctx.message.author.bot:
            return False

        # Ignore anyone in the ineligible list
        if ctx.author.id in self.ineligible:
            return False

        # Ignore messages outside of tracked categories
        if ctx.channel.category_id not in config.extensions.xp.categories_counted.value:
            return False

        # Ignore messages that are too short
        if len(ctx.message.clean_content) < 20:
            return False

        prefix = await self.bot.get_prefix(ctx.message)

        # Ignore messages that are bot commands
        if ctx.message.clean_content.startswith(prefix):
            return False

        # Ignore messages that are factoid calls
        if "factoids" in config.enabled_extensions:
            factoid_prefix = prefix = config.extensions.factoids.prefix.value
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
        self: Self, config: munch.Munch, ctx: commands.Context, content: str, _: bool
    ) -> None:
        """Updates XP for the given user.
        Message has already been validated when you reach this function.

        Args:
            config (munch.Munch): The guild config for the running bot
            ctx (commands.Context): The context in which the message was sent in
            content (str): The string content of the message
        """
        current_XP = await get_current_XP(self.bot, ctx.author, ctx.guild)
        new_XP = random.randint(10, 20)

        await update_current_XP(self.bot, ctx.author, ctx.guild, (current_XP + new_XP))

        await self.apply_level_ups(ctx.author, (current_XP + new_XP))

        self.ineligible[ctx.author.id] = True

    async def apply_level_ups(self: Self, user: discord.Member, new_xp: int) -> None:
        """This function will determine if a user leveled up and apply the proper roles

        Args:
            user (discord.Member): The user who just gained XP
            new_xp (int): The new amount of XP the user has
        """
        config = self.bot.guild_configs[str(user.guild.id)]
        levels = config.extensions.xp.level_roles.value

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
