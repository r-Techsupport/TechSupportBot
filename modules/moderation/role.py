"""The file to hold the role extension
This extension is slash commands"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from discord import app_commands

import configuration
from core import auxiliary, cogs

if TYPE_CHECKING:
    import bot


async def setup(bot: bot.TechSupportBot) -> None:
    """Adding config and the cog to the bot

    Args:
        bot (bot.TechSupportBot): The bot object
    """
    await bot.add_cog(RoleGiver(bot=bot))


class RoleGiver(cogs.BaseCog):
    """The main class for the role commands

    Attributes:
        role_group (app_commands.Group): The group for the /role commands

    Args:
        bot (bot.TechSupportBot): The bot object, is used for registering context menu commands
    """

    def __init__(self: Self, bot: bot.TechSupportBot) -> None:
        super().__init__(bot=bot)
        self.ctx_menu = app_commands.ContextMenu(
            name="Manage roles",
            callback=self.assign_role_command,
        )
        self.bot.tree.add_command(self.ctx_menu)

    role_group: app_commands.Group = app_commands.Group(name="role", description="...")

    async def preconfig(self: Self) -> None:
        """This setups the global lock on the role command, to avoid conflicts"""
        self.locked = set()

    @role_group.command(
        name="self",
        description="Assign or remove roles from yourself",
    )
    async def self_role(self: Self, interaction: discord.Interaction) -> None:
        """The base of the self role command

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        # Interaction user roles
        current_roles = getattr(interaction.user, "roles", [])

        # Get the roles map
        roles_map = configuration.get_config_entry(
            interaction.guild.id, "role_self_assign_map"
        )

        allowed_roles_list = []

        # Build the allowed roles list
        for assignable_role in roles_map:
            for allowed_role in roles_map[assignable_role]:
                discord_allowed_role = discord.utils.get(
                    interaction.guild.roles, id=int(allowed_role)
                )
                if discord_allowed_role in current_roles:
                    allowed_roles_list.append(assignable_role)
                    break

        if len(allowed_roles_list) == 0:
            embed = auxiliary.prepare_deny_embed(
                message="You cannot assign yourself any roles right now"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Get needed config items
        allowed_to_execute = configuration.get_config_entry(
            interaction.guild.id, "role_allow_self_assign"
        )

        # Call the base function
        await self.role_command_base(
            interaction, allowed_roles_list, allowed_to_execute, interaction.user
        )

    @role_group.command(
        name="manage",
        description="Modify roles on a given user",
    )
    async def assign_role(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """The base of the wide assign command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            member (discord.Member): The member to apply roles to
        """
        await self.assign_role_command(interaction=interaction, member=member)

    async def assign_role_command(
        self: Self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Serves as the core logic for the /role manage command
        This is the direct entry point for the context menu

        Args:
            interaction (discord.Interaction): The interaction that triggered this
            member (discord.Member): The member to modify roles of
        """
        # Get needed config items
        roles = configuration.get_config_entry(
            interaction.guild.id, "role_all_assignable_roles"
        )
        allowed_to_execute = configuration.get_config_entry(
            interaction.guild.id, "role_allow_all_assign"
        )

        # Call the base function
        await self.role_command_base(interaction, roles, allowed_to_execute, member)

    async def role_command_base(
        self: Self,
        interaction: discord.Interaction,
        assignable_roles: list[str],
        allowed_roles: list[str],
        member: discord.Member,
    ) -> None:
        """The base processor for the role commands
        Checks permissions and config, and sends the view

        Args:
            interaction (discord.Interaction): The interaction that called this command
            assignable_roles (list[str]): A list of role IDs that are assignabled for this command
            allowed_roles (list[str]): A list of roles that are allowed to execute this command
            member (discord.Member): The member to assign roles to
        """
        role_options = self.generate_options(
            member, interaction.guild, assignable_roles
        )

        can_execute = self.check_permissions(
            interaction.user, interaction.guild, allowed_roles
        )
        if not can_execute:
            embed = auxiliary.prepare_deny_embed(
                "You are not allowed to execute this command"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if len(role_options) == 0:
            embed = auxiliary.prepare_deny_embed("No self assignable roles are setup")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        identifier = f"{member.id}-{member.guild.id}"

        if identifier in self.locked:
            embed = auxiliary.prepare_deny_embed(
                f"{member} is currently being modified by someone else. Try again"
                " later."
            )
            await interaction.response.send_message(
                content=None,
                embed=embed,
                ephemeral=True,
            )
            return
        self.locked.add(identifier)

        view = RoleView(role_options)
        await interaction.response.send_message(
            content=f"Select what roles should be assigned to {member} below",
            ephemeral=True,
            view=view,
        )
        await view.wait()

        # If we cancelled, assign no roles and release the lock
        if view.select.cancelled:
            embed = auxiliary.prepare_deny_embed(
                "You cancelled editing roles. No changes were made"
            )
            await interaction.edit_original_response(embed=embed, view=None)
            self.locked.remove(identifier)
            return

        # In the event of a timeout, do not remove any roles, and release the lock
        if view.select.timeout:
            embed = auxiliary.prepare_deny_embed("This menu timed out")
            await interaction.edit_original_response(embed=embed, view=None)
            self.locked.remove(identifier)
            return

        # Modify roles, tell user roles were modified
        await self.modify_roles(
            config_roles=assignable_roles,
            new_roles=view.select.values,
            guild=interaction.guild,
            user=member,
            reason=f"Role command, ran by {interaction.user}",
            interaction=interaction,
        )
        # Remove user from the lock
        self.locked.remove(identifier)

    def check_permissions(
        self: Self, user: discord.User, guild: discord.Guild, roles: list[str]
    ) -> bool:
        """A function to return a boolean value if the user can run role commands or not

        Args:
            user (discord.User): The user executing the command
            guild (discord.Guild): The guild the command was run in
            roles (list[str]): A list of the roles allowed to execute

        Returns:
            bool: True if can execute, false if cannot
        """
        if len(roles) == 0:
            return False

        for role in roles:
            real_role = discord.utils.get(guild.roles, name=role)
            if real_role in getattr(user, "roles", []):
                return True

        return False

    def generate_options(
        self: Self, user: discord.Member, guild: discord.Guild, roles: list[str]
    ) -> list[discord.SelectOption]:
        """A function to turn a list of roles into a set of SelectOptions

        Args:
            user (discord.Member): The user that will be getting the roles applied
            guild (discord.Guild): The guild that the roles are from
            roles (list[str]): A list of roles by ID to add to the options

        Returns:
            list[discord.SelectOption]: A list of SelectOption with defaults set
        """
        options = []

        for role_id in roles:
            default = False

            # First, get the role
            role = discord.utils.get(guild.roles, id=int(role_id))
            if not role:
                continue

            # Second, check if user has role
            if role in getattr(user, "roles", []):
                default = True

            # Third, the option to the list with relevant default
            options.append(discord.SelectOption(label=role.name, default=default))
        return options

    async def modify_roles(
        self: Self,
        config_roles: list[str],
        new_roles: list[str],
        guild: discord.Guild,
        user: discord.Member,
        reason: str,
        interaction: discord.Interaction,
    ) -> None:
        """Modifies a set of roles based on an input and reference list

        Args:
            config_roles (list[str]): The list of roles by ID allowed to be modified
            new_roles (list[str]): The list of roles from the config_roles that should be assigned
                to the user. Any roles not on this list will be removed
            guild (discord.Guild): The guild to assign the roles in
            user (discord.Member): The member to assign roles to
            reason (str): The reason to add to the audit log
            interaction (discord.Interaction): The interaction to respond to
        """
        added_roles = []
        removed_roles = []

        for role_id in config_roles:
            real_role = discord.utils.get(guild.roles, id=int(role_id))
            if not real_role:
                continue

            user_roles = getattr(user, "roles", [])

            # If the role was requested to be added
            if real_role.name in new_roles and real_role not in user_roles:
                await user.add_roles(real_role, reason=reason)
                added_roles.append(real_role.name)
            elif real_role.name not in new_roles and real_role in user_roles:
                await user.remove_roles(real_role, reason=reason)
                removed_roles.append(real_role.name)

        if not added_roles and not removed_roles:
            embed = auxiliary.prepare_confirm_embed(
                "Command was successful, but no roles were modified"
            )
        else:
            embed = auxiliary.prepare_confirm_embed("Roles were successfully modified")
            if added_roles:
                embed.add_field(name="Added roles:", value="\n".join(added_roles))
            if removed_roles:
                embed.add_field(name="Removed roles:", value="\n".join(removed_roles))
        await interaction.edit_original_response(content=None, embed=embed, view=None)


class RoleSelectView(discord.ui.Select):
    """This holds the select object for a list of roles

    Args:
        role_list (list[str]): A list of SelectOption to be in the dropdown
    """

    def __init__(self: Self, role_list: list[str]) -> None:
        super().__init__(
            placeholder="Select roles...",
            min_values=0,
            max_values=len(role_list),
            options=role_list,
            row=0,
        )
        self.timeout = True
        self.cancelled = False

    async def callback(self: Self, interaction: discord.Interaction) -> None:
        """What happens when the select menu has been used

        Args:
            interaction (discord.Interaction): The interaction that called this select object
        """
        self.timeout = False
        self.view.stop()

    async def on_timeout(self: Self) -> None:
        """What happens when the view timesout. This is to prevent all roles from being removed."""
        self.values = None
        self.view.stop()


class RoleView(discord.ui.View):
    """This is the view that will hold only the dropdown
    Adds the dropdown and does nothing else
    Args:
        role_list (list[str]): The list of SelectOptions to add to the dropdown
    """

    def __init__(self: Self, role_list: list[str]) -> None:
        super().__init__()
        # Adds the dropdown to our view object.
        self.select = RoleSelectView(role_list)
        self.add_item(self.select)

    async def on_timeout(self: Self) -> None:
        """What happens when the view times out."""
        self.select.values = None
        self.stop()

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="❌",
        row=1,
    )
    async def cancel_button(
        self: Self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """A button to instatly cancel the role assignment

        Args:
            self (Self): _description_
            interaction (discord.Interaction): The interaction that pressed this button
            button (discord.ui.Button): The button object
        """

        self.select.cancelled = True
        self.stop()
