from typing import Union

import discord
from base import auxiliary, cogs
from discord import app_commands


async def setup(bot):
    """Adding the poll and recation to the config file."""
    await bot.add_cog(ProtectCommands(bot=bot))


class ProtectCommands(cogs.BaseCog):
    ALERT_ICON_URL = (
        "https://cdn.icon-icons.com/icons2/2063/PNG/512/"
        + "alert_danger_warning_notification_icon_124692.png"
    )

    async def preconfig(self) -> None:
        # Get the moderation function cog to allow it to be called
        self.moderation = self.bot.get_cog("ModerationFunctions")

    # Commands

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.command(name="ban", description="Bans a user from the guild")
    async def handle_ban_user(
        self,
        interaction: discord.Interaction,
        target: discord.User,
        reason: str,
        delete_days: int = None,
    ) -> None:
        """The ban slash command. This checks that the permissions are correct
        and that the user is not already banned

        Args:
            interaction (discord.Interaction): The interaction that called this command
            target (discord.User): The target to ban
            reason (str): The reason the person is getting banned
            delete_days (int, optional): How many days of messages to delete. Defaults to None.
        """
        # Ensure we can ban the person
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="ban"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        async for ban in interaction.guild.bans(limit=None):
            if target == ban.user:
                embed = auxiliary.prepare_deny_embed(message="User is already banned.")
                await interaction.response.send_message(embed=embed)
                return

        if not delete_days:
            config = await self.bot.get_context_config(guild=interaction.guild)
            delete_days = config.extensions.protect.ban_delete_duration.value

        # Ban the user using the core moderation cog
        result = await self.moderation.ban_user(
            guild=interaction.guild,
            user=target,
            delete_days=delete_days,
            reason=f"{reason} - banned by {interaction.user}",
        )
        if not result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when banning {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        await self.send_command_usage_alert(
            interaction=interaction,
            command=f"/ban target: {target.display_name}, reason: {reason}, delete_days: {delete_days}",
            guild=interaction.guild,
            target=target,
        )
        embed = self.generate_response_embed(user=target, action="ban", reason=reason)
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.checks.bot_has_permissions(ban_members=True)
    @app_commands.command(name="unban", description="Unbans a user from the guild")
    async def handle_unban_user(
        self, interaction: discord.Interaction, target: discord.User, reason: str
    ):
        permission_check = await self.permission_check(
            invoker=interaction.user, target=target, action_name="unban"
        )
        if permission_check:
            embed = auxiliary.prepare_deny_embed(message=permission_check)
            await interaction.response.send_message(embed=embed)
            return

        is_banned = False

        async for ban in interaction.guild.bans(limit=None):
            if target == ban.user:
                is_banned = True

        if not is_banned:
            embed = auxiliary.prepare_deny_embed(message=f"{target} is not banned")
            await interaction.response.send_message(embed=embed)
            return

        result = await self.moderation.unban_user(
            guild=interaction.guild,
            user=target,
            reason=f"{reason} - unbanned by {interaction.user}",
        )
        if not result:
            embed = auxiliary.prepare_deny_embed(
                message=f"Something went wrong when unbanning {target}"
            )
            await interaction.response.send_message(embed=embed)
            return

        await self.send_command_usage_alert(
            interaction=interaction,
            command=f"/unban target: {target.display_name}, reason: {reason}",
            guild=interaction.guild,
            target=target,
        )
        embed = self.generate_response_embed(user=target, action="unban", reason=reason)
        await interaction.response.send_message(content=target.mention, embed=embed)

    @app_commands.command(name="kick", description="Kicks a user from the guild")
    async def handle_kick_user(
        self, interaction: discord.Interaction, target: discord.Member, reason: str
    ):
        await interaction.channel.send("kick command")

    @app_commands.command(name="mute", description="Times out a user")
    async def handle_mute_user(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
        duration: str = None,
    ):
        await interaction.channel.send("mute command")

    @app_commands.command(name="unmute", description="Removes timeout from a user")
    async def handle_unmute_user(
        self, interaction: discord.Interaction, target: discord.Member, reason: str
    ):
        await interaction.channel.send("unmute command")

    @app_commands.command(name="warn", description="Warns a user")
    async def handle_warn_user(
        self, interaction: discord.Interaction, target: discord.Member, reason: str
    ):
        await interaction.channel.send("warn command")

    @app_commands.command(name="unwarn", description="Unwarns a user")
    async def handle_unwarn_user(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        reason: str,
        warning: str,
    ):
        await interaction.channel.send("unwarn command")

    # Helper functions

    async def permission_check(
        self,
        invoker: discord.Member,
        target: Union[discord.User, discord.Member],
        action_name: str,
    ) -> str:
        """Checks permissions to ensure the command should be executed. This checks:
        If the target is the invoker
        If the target is the bot
        If the user is in the server
        If the target has an immune role
        If the target can be banned by the bot
        If the invoker has a higher role than the target

        Args:
            invoker (discord.Member): The invoker of the action.
                Either will be the user who ran the command, or the bot itself
            target (Union[discord.User, discord.Member]): The target of the command.
                Can be a user or member.
            action_name (str): The action name to be displayed in messages

        Returns:
            str: The rejection string, if one exists. Otherwise, None is returned
        """
        config = await self.bot.get_context_config(guild=invoker.guild)
        # Check to see if executed on author
        if invoker == target:
            return f"You cannot {action_name} yourself"

        # Check to see if executed on bot
        if target == self.bot.user:
            return f"It would be silly to {action_name} myself"

        # Check to see if User or Member
        if isinstance(target, discord.User):
            return None

        # Check to see if target has any immune roles
        for name in config.extensions.protect.immune_roles.value:
            role_check = discord.utils.get(target.guild.roles, name=name)
            if role_check and role_check in getattr(target, "roles", []):
                return f"You cannot {action_name} {target} because they have `{role_check}` role"

        # Check to see if the Bot can execute on the target
        if invoker.guild.get_member(int(self.bot.user.id)).top_role <= target.top_role:
            return f"Bot does not have enough permissions to {action_name} `{target}`"

        # Check to see if author top role is higher than targets
        if invoker.top_role <= target.top_role:
            return f"You do not have enough permissions to {action_name} `{target}`"

        return None

    def generate_response_embed(
        self, user: discord.Member, action: str, reason: str
    ) -> discord.Embed:
        """This generates a simple embed to be displayed in the chat where the command was called.

        Args:
            user (discord.Member): The user who was actioned against
            action (str): The string representation of the action type
            reason (str): The reason the action was taken

        Returns:
            discord.Embed: The formatted embed ready to be sent
        """
        embed = discord.Embed(
            title="Chat Protection", description=f"{action.upper()} `{user}`"
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.color = discord.Color.gold()

        return embed

    async def send_command_usage_alert(
        self,
        interaction: discord.Interaction,
        command: str,
        guild: discord.Guild,
        target: discord.Member,
    ) -> None:
        config = await self.bot.get_context_config(guild=guild)

        try:
            alert_channel = guild.get_channel(
                int(config.extensions.protect.alert_channel.value)
            )
        except TypeError:
            alert_channel = None

        if not alert_channel:
            return

        embed = discord.Embed(title="Protect Alert")

        embed.add_field(name="Command", value=f"`{command}`", inline=False)
        embed.add_field(
            name="Channel",
            value=f"{interaction.channel.name} ({interaction.channel.mention})",
        )
        embed.add_field(
            name="Invoking User",
            value=f"{interaction.user.display_name} ({interaction.user.mention})",
        )
        embed.add_field(
            name="Target",
            value=f"{target.display_name} ({target.mention})",
        )

        embed.set_thumbnail(url=self.ALERT_ICON_URL)
        embed.color = discord.Color.red()

        await alert_channel.send(embed=embed)
