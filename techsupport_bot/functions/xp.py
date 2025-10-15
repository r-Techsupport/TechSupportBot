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
        self: Self, config: munch.Munch, ctx: commands.Context, content: str
    ) -> bool:
        """A match function to determine if somehting should be reacted to

        Args:
            config (munch.Munch): The guild config for the running bot
            content (str): The string content of the message

        Returns:
            bool: True if there needs to be a reaction, False otherwise
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
        """The function to generate and add reactions

        Args:
            config (munch.Munch): The guild config for the running bot
            ctx (commands.Context): The context in which the message was sent in
            content (str): The string content of the message
        """
        current_XP = await get_current_XP(self.bot, ctx.author, ctx.guild)
        new_XP = random.randint(10, 50)

        await update_current_XP(self.bot, ctx.author, ctx.guild, (current_XP + new_XP))

        await self.apply_level_ups(ctx.author, current_XP, (current_XP + new_XP))

        await ctx.channel.send(
            f"{ctx.author.display_name}: XP. New: {new_XP}, Total: {current_XP+new_XP}"
        )
        self.ineligible[ctx.author.id] = True

    async def apply_level_ups(
        self: Self, user: discord.Member, old_xp: int, new_xp: int
    ) -> None:
        """This function will determine if a user leveled up and apply the proper roles

        Args:
            user (discord.Member): The user who just gained XP
            old_xp (int): The old amount of XP the user had
            new_xp (int): The new amount of XP the user has
        """
        old_level = None
        new_level = None

        config = self.bot.guild_configs[str(user.guild.id)]
        levels = config.extensions.xp.level_roles.value
        print(levels)
        if len(levels) == 0:
            return

        old_level = max(
            ((int(xp), role_id) for xp, role_id in levels.items() if old_xp >= int(xp)),
            default=(-1, None),
            key=lambda t: t[0],
        )[1]

        new_level = max(
            ((int(xp), role_id) for xp, role_id in levels.items() if new_xp >= int(xp)),
            default=(-1, None),
            key=lambda t: t[0],
        )[1]

        if old_level != new_level:
            guild = user.guild

            if old_level:
                old_role = guild.get_role(old_level)
                if old_role in user.roles:
                    await user.remove_roles(
                        old_role, reason="Level up - replacing old level role"
                    )

            if new_level:
                new_role = guild.get_role(new_level)
                if new_role not in user.roles:
                    await user.add_roles(
                        new_role, reason="Level up - new level role applied"
                    )

            return


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
