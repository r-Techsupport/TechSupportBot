"""Store per-guild feature bans as a bitmask."""

from __future__ import annotations

from enum import IntFlag, unique
from itertools import batched
from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import ui
from core import auxiliary, cogs
from database.schema import FeatureBan
from modules.moderation import moderator, modlog

if TYPE_CHECKING:
    import bot


@unique
class FeatureFlag(IntFlag):
    """Features that can be banned. Keep assigned bits stable for stored bans.

    Attributes:
        NONE (int): Indicates no feature bans
        APPLICATION (int): Ban from Applications
        HANGMAN (int): Ban from Hangman
        MODMAIL (int): Ban from Modmail
        REPORT (int): Ban from Reports
    """

    NONE: int = 0
    APPLICATION: int = 1 << 0
    HANGMAN: int = 1 << 1
    MODMAIL: int = 1 << 2
    REPORT: int = 1 << 3


async def setup(bot: bot.TechSupportBot) -> None:
    """Register the feature ban commands.

    Args:
        bot (bot.TechSupportBot): The bot loading the extension
    """
    await bot.add_cog(FeatureBans(bot=bot))


class FeatureBans(cogs.BaseCog):
    """Commands for managing feature bans in a guild.

    Attributes:
        feature_group (app_commands.Group): The group for the /feature commands
    """

    feature_group: app_commands.Group = app_commands.Group(
        name="feature", description="Manage feature bans", guild_only=True
    )

    @app_commands.checks.has_permissions(ban_members=True)
    @feature_group.command(name="ban", description="Ban a user from a feature")
    async def ban_feature(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        feature: str,
        reason: str,
    ) -> None:
        """Ban the selected user from a feature.

        Args:
            interaction (discord.Interaction): The command interaction
            user (discord.Member): The member to ban
            feature (str): The feature to ban the member from
            reason (str): The reason for the ban
        """
        await self.update_feature_ban(interaction, user, feature, reason, banned=True)

    @app_commands.checks.has_permissions(ban_members=True)
    @feature_group.command(name="unban", description="Unban a user from a feature")
    async def unban_feature(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        feature: str,
        reason: str,
    ) -> None:
        """Remove the selected user's ban from a feature.

        Args:
            interaction (discord.Interaction): The command interaction
            user (discord.Member): The member to unban
            feature (str): The feature to unban the member from
            reason (str): The reason for the unban
        """
        await self.update_feature_ban(interaction, user, feature, reason, banned=False)

    @app_commands.checks.has_permissions(ban_members=True)
    @feature_group.command(
        name="list-bans", description="List users banned from a feature"
    )
    async def list_bans(
        self: Self, interaction: discord.Interaction, feature: str
    ) -> None:
        """List users banned from the selected feature in this guild.

        Args:
            interaction (discord.Interaction): The command interaction
            feature (str): The feature to list bans for
        """
        flag = FeatureFlag.__members__.get(feature.strip().upper().replace(" ", "_"))
        if not flag:
            embed = auxiliary.prepare_deny_embed("Choose a valid feature.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        rows = await FeatureBan.select(FeatureBan.user_id, FeatureBan.ban_flags).where(
            FeatureBan.guild_id == str(interaction.guild_id)
        )
        users = []
        for row in rows:
            if not row["ban_flags"] & flag:
                continue

            user_id = int(row["user_id"])
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                username = user.name
            except discord.NotFound:
                username = f"Unknown user ({user_id})"
            users.append(f"<@{user_id}> - `{username}`")
        label = flag.name.replace("_", " ").title()
        if not users:
            embed = auxiliary.prepare_deny_embed(f"No users are banned from {label}.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        pages = [
            discord.Embed(title=f"{label} bans", description="\n".join(page))
            for page in batched(users, 20)
        ]
        if len(pages) == 1:
            await interaction.followup.send(embed=pages[0], ephemeral=True)
        else:
            await ui.PaginateView().send(
                interaction.channel,
                interaction.user,
                pages,
                interaction,
                ephemeral=True,
            )

    @app_commands.checks.has_permissions(ban_members=True)
    @feature_group.command(
        name="lookup", description="Show a user's feature ban status"
    )
    async def lookup(
        self: Self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """List the features the selected user is banned from in this guild.

        Args:
            interaction (discord.Interaction): The command interaction
            user (discord.User): The user whose bans to look up
        """
        banned_flags = await get_feature_bans(interaction.guild_id, user.id)
        features = [
            f"- {flag.name.replace('_', ' ').title()}"
            for flag in FeatureFlag
            if banned_flags & flag
        ]
        description = "\n".join(features) if features else "No feature bans."
        embed = discord.Embed(
            title=f"Feature bans for {user}",
            description=description,
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @list_bans.autocomplete("feature")
    @ban_feature.autocomplete("feature")
    @unban_feature.autocomplete("feature")
    async def feature_autocomplete(
        self: Self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest features that the selected command can change for the user.

        Args:
            interaction (discord.Interaction): The autocomplete interaction
            current (str): The current text in the feature field

        Returns:
            list[app_commands.Choice[str]]: Matching features for the selected user
        """
        if not interaction.permissions.ban_members:
            return []

        features = list(FeatureFlag)
        if interaction.command.name != "list-bans":
            # Autocomplete can receive a discord.Object containing only the user ID.
            user = getattr(interaction.namespace, "user", None)
            if user is None:
                return []
            banned_flags = await get_feature_bans(interaction.guild_id, user.id)
            show_banned = interaction.command.name == "unban"
            features = [
                flag for flag in features if bool(banned_flags & flag) == show_banned
            ]
        search = current.casefold()
        return [
            app_commands.Choice(
                name=flag.name.replace("_", " ").title(), value=flag.name
            )
            for flag in features
            if search in flag.name.replace("_", " ").casefold()
        ][:25]

    async def update_feature_ban(
        self: Self,
        interaction: discord.Interaction,
        user: discord.Member,
        feature: str,
        reason: str,
        banned: bool,
    ) -> None:
        """Validate the selected feature and update the user's ban.

        Args:
            interaction (discord.Interaction): The command interaction
            user (discord.Member): The member whose ban is being changed
            feature (str): The selected or typed feature name
            reason (str): The reason for changing the ban
            banned (bool): Whether to add or remove the ban
        """
        flag = FeatureFlag.__members__.get(feature.strip().upper().replace(" ", "_"))
        action = "banned" if banned else "unbanned"
        if not flag:
            embed = auxiliary.prepare_deny_embed("Choose a valid feature.")
        else:
            denial = await moderator.permission_check(
                bot=self.bot,
                invoker=interaction.user,
                target=user,
                action_name=action[:-3],
            )
            if denial:
                embed = auxiliary.prepare_deny_embed(denial)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            label = flag.name.replace("_", " ").title()
            guild_id = interaction.guild.id
            if await is_feature_banned(guild_id, user.id, flag) == banned:
                status = "already banned" if banned else "not banned"
                embed = auxiliary.prepare_deny_embed(
                    f"{user.mention} is {status} from {label}."
                )
            else:
                await set_feature_ban(guild_id, user.id, flag, banned=banned)
                embed = auxiliary.prepare_confirm_embed(
                    f"{user.mention} is {action} from {label}."
                )
                await modlog.log_action(
                    bot=self.bot,
                    action_type=f"{label} {action[:-3]}",
                    guild=interaction.guild,
                    member=user,
                    moderator=interaction.user,
                    channel=interaction.channel,
                    reason=reason,
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def get_ban_entry(guild_id: int, user_id: int) -> FeatureBan | None:
    """Find the ban record for a guild and user.

    Args:
        guild_id (int): The Discord guild ID
        user_id (int): The Discord user ID

    Returns:
        FeatureBan | None: The stored record, if one exists
    """
    return (
        await FeatureBan.objects()
        .where(FeatureBan.guild_id == str(guild_id), FeatureBan.user_id == str(user_id))
        .first()
    )


async def get_feature_bans(guild_id: int, user_id: int) -> FeatureFlag:
    """Get the user's banned features in a guild.

    Args:
        guild_id (int): The Discord guild ID
        user_id (int): The Discord user ID

    Returns:
        FeatureFlag: The stored flags, or FeatureFlag.NONE if no ban exists
    """
    entry = await get_ban_entry(guild_id, user_id)
    return FeatureFlag(entry.ban_flags) if entry is not None else FeatureFlag.NONE


async def is_feature_banned(guild_id: int, user_id: int, feature: FeatureFlag) -> bool:
    """Check whether the user is banned from any of the requested features.

    Args:
        guild_id (int): The Discord guild ID
        user_id (int): The Discord user ID
        feature (FeatureFlag): One or more features to check

    Returns:
        bool: Whether any requested feature is banned
    """
    return bool(await get_feature_bans(guild_id, user_id) & feature)


async def set_feature_ban(
    guild_id: int, user_id: int, features: FeatureFlag, banned: bool
) -> FeatureFlag:
    """Ban or unban the requested features and return the updated flags.

    Args:
        guild_id (int): The Discord guild ID
        user_id (int): The Discord user ID
        features (FeatureFlag): One or more features to update
        banned (bool): True to add the flags, False to clear them

    Returns:
        FeatureFlag: The resulting set of banned features
    """
    entry = await get_ban_entry(guild_id, user_id)
    current_flags = entry.ban_flags if entry is not None else 0

    if banned:
        updated_flags = current_flags | int(features)
    else:
        updated_flags = current_flags & ~int(features)

    if updated_flags == current_flags:
        return FeatureFlag(current_flags)

    if entry is None:
        await FeatureBan(
            guild_id=str(guild_id), user_id=str(user_id), ban_flags=updated_flags
        ).save()
    elif updated_flags:
        entry.ban_flags = updated_flags
        await entry.save(columns=[FeatureBan.ban_flags])
    else:
        await entry.remove()

    return FeatureFlag(updated_flags)
