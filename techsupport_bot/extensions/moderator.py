from typing import Union

import discord
from base import auxiliary, cogs
from discord import app_commands


async def setup(bot):
    """Adding the poll and recation to the config file."""
    await bot.add_cog(ProtectCommands(bot=bot))


class ProtectCommands(cogs.BaseCog):
    @app_commands.command(name="ban", description="Bans a user from the guild")
    async def handle_ban_user(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str,
        delete_days: int = None,
    ):
        permission_check = await self.permission_check(
            invoker=interaction.user, target=user, action_name="ban"
        )
        if permission_check:
            await interaction.response.send_message(permission_check)
            return
        await interaction.response.send_message("ban command")

    @app_commands.command(name="unban", description="Unbans a user from the guild")
    async def handle_unban_user(
        self, interaction: discord.Interaction, user: discord.User, reason: str
    ):
        await interaction.channel.send("unban command")

    @app_commands.command(name="kick", description="Kicks a user from the guild")
    async def handle_kick_user(
        self, interaction: discord.Interaction, user: discord.Member, reason: str
    ):
        await interaction.channel.send("kick command")

    @app_commands.command(name="mute", description="Times out a user")
    async def handle_mute_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        duration: str = None,
    ):
        await interaction.channel.send("mute command")

    @app_commands.command(name="unmute", description="Removes timeout from a user")
    async def handle_unmute_user(
        self, interaction: discord.Interaction, user: discord.Member, reason: str
    ):
        await interaction.channel.send("unmute command")

    @app_commands.command(name="warn", description="Warns a user")
    async def handle_warn_user(
        self, interaction: discord.Interaction, user: discord.Member, reason: str
    ):
        await interaction.channel.send("warn command")

    @app_commands.command(name="unwarn", description="Unwarns a user")
    async def handle_unwarn_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
        warning: str,
    ):
        await interaction.channel.send("unwarn command")

    async def permission_check(
        self,
        invoker: discord.Member,
        target: Union[discord.User, discord.Member],
        action_name: str,
    ) -> str:
        """_summary_

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
