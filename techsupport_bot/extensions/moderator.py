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
        await interaction.channel.send("ban command")

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
        self, invoker: discord.User, target: discord.User
    ) -> str:
        ...
