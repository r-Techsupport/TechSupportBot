"""The file to hold the role extension
This extension is slash commands"""

import base
import discord
import ui
from discord import app_commands


async def setup(bot):
    """Adding config and the cog to the bot

    Args:
        bot (commands.Bot): The bot object
    """
    config = bot.ExtensionConfig()
    config.add(
        key="self_assignable_roles",
        datatype="list",
        title="All roles people can assign themselves",
        description="The list of roles by name that people can assign themselves",
        default=[],
    )
    config.add(
        key="allow_self_assign",
        datatype="list",
        title="List of roles allowed to use /role self",
        description="The list of roles that are allowed to assign themselves roles",
        default=[],
    )
    config.add(
        key="all_assignable_roles",
        datatype="list",
        title="Roles moderators can assign",
        description="The list of roles by name that moderators can assign to people",
        default=[],
    )
    config.add(
        key="allow_all_assign",
        datatype="list",
        title="List of roles allowed to use /role assign",
        description="The list of roles that are allowed to assign others roles",
        default=[],
    )
    await bot.add_cog(RoleGiver(bot=bot))
    bot.add_extension_config("role", config)


class RoleGiver(base.BaseCog):
    """The main class for the role commands"""

    role_group = app_commands.Group(name="role", description="...")

    @role_group.command(name="self")
    async def self_role(self, interaction):
        """The base of the self role command

        Args:
            interaction (discord.Interaction): The interaction that called this command
        """
        # Pull config
        config = await self.bot.get_context_config(guild=interaction.guild)

        # Get needed config items
        roles = config.extensions.role.self_assignable_roles.value
        allowed_to_execute = config.extensions.role.allow_self_assign.value

        # Call the base function
        await self.role_command_base(
            interaction, roles, allowed_to_execute, interaction.user
        )

    @role_group.command(name="assign")
    async def assign_role(self, interaction, member: discord.Member):
        """The base of the wide assign command

        Args:
            interaction (discord.Interaction): The interaction that called this command
            member (discord.Member): The member to apply roles to
        """
        # Pull config
        config = await self.bot.get_context_config(guild=interaction.guild)

        # Get needed config items
        roles = config.extensions.role.all_assignable_roles.value
        allowed_to_execute = config.extensions.role.allow_all_assign.value

        # Call the base function
        await self.role_command_base(interaction, roles, allowed_to_execute, member)

    async def role_command_base(
        self, interaction, assignable_roles, allowed_roles, member
    ):
        """The base processor for the role commands
        Checks permissions and config, and sends the view

        Args:
            interaction (discord.Interaction): The interaction that called this command
            assignable_roles (list): A list of roles that are assignabled for this command
            allowed_roles (list): A list of roles that are allowed to execute this command
            member (discord.Member): The member to assign roles to
        """
        role_options = self.generate_options(
            member, interaction.guild, assignable_roles
        )

        if len(allowed_roles) == 0:
            await interaction.response.send_message(
                "Nobody is allowed to execute this command", ephemeral=True
            )
            return

        for role in allowed_roles:
            real_role = discord.utils.get(interaction.guild.roles, name=role)
            if real_role not in getattr(interaction.user, "roles", []):
                await interaction.response.send_message(
                    "You are not allowed to execute this command", ephemeral=True
                )
                return

        if len(role_options) == 0:
            await interaction.response.send_message(
                "No self assignable roles are setup", ephemeral=True
            )
            return

        view = ui.SelectView(role_options)
        await interaction.response.send_message(
            content=f"Select what roles should be assigned to {member} below",
            ephemeral=True,
            view=view,
        )
        await view.wait()
        await self.modify_roles(
            config_roles=assignable_roles,
            new_roles=view.select.values,
            guild=interaction.guild,
            user=member,
        )

    def generate_options(self, user, guild, roles):
        """A function to turn a list of roles into a set of SelectOptions

        Args:
            user (discord.Member): The user that will be getting the roles applied
            guild (discord.Guild): The guild that the roles are from
            roles (list): A list of roles by name to add to the options

        Returns:
            list: A list of SelectOption with defaults set
        """
        options = []

        for role_name in roles:
            default = False

            # First, get the role
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                continue

            # Second, check if user has role
            if role in getattr(user, "roles", []):
                default = True

            # Third, the option to the list with relevant default
            options.append(discord.SelectOption(label=role_name, default=default))
        return options

    async def modify_roles(self, config_roles, new_roles, guild, user):
        """Modifies a set of roles based on an input and reference list

        Args:
            config_roles (list): The list of roles allowed to be modified
            new_roles (list): The list of roles from the config_roles that should be assigned to
                the user. Any roles not on this list will be removed
            guild (discord.Guild): The guild to assign the roles in
            user (discord.Member): The member to assign roles to
        """
        for role_name in config_roles:
            real_role = discord.utils.get(guild.roles, name=role_name)
            if not real_role:
                continue

            user_roles = getattr(user, "roles", [])

            # If the role was requested to be added
            if real_role.name in new_roles and real_role not in user_roles:
                await user.add_roles(real_role)
            elif real_role.name not in new_roles and real_role in user_roles:
                await user.remove_roles(real_role)
