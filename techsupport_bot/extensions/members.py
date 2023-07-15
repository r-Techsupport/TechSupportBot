"""
Name: Members
Info: Lists all users who have a specified role
Unit tests: None
Config: None
API: None
Databases: None
Models: None
Subcommands: None
Defines: get_members_with_role
"""
import datetime
import io

import base
import discord
import util
import yaml
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add the member command to config."""
    await bot.add_cog(Members(bot=bot))


class Members(base.BaseCog):
    """Class for the Member command on the discord bot."""

    async def get_members_with_role(
        self, ctx: commands.Context, member_list: list, role_name: str
    ):
        """
        Gets a list of members with role_name for the invokers guild.

        Args:
            ctx (command.Context): Used to return a message
            member_list (list): A list of members to parse
            role (str): The role to check for
        """
        # All roles are handled using a shorthand for loop because all
        # `.roles` attributes have lists of role objects, we want the names.

        role = ""
        # Gets the role by an id if the supplied name is an id
        if role_name.isnumeric():
            role = discord.utils.get(ctx.guild.roles, id=int(role_name))

        # If it couldn't find it, tries to get it by the name instead
        if not role:
            role = discord.utils.get(ctx.guild.roles, name=role_name)

        if not role:
            await auxiliary.send_deny_embed(
                message=f"I couldn't find the role `{role_name}`", channel=ctx.channel
            )
            return

        # Iterates through members, appends their info to a yaml file
        yaml_output_data = []
        for member in member_list:
            if discord.utils.get(member.roles, name=role.name):
                data = {
                    "id": member.id,
                    "roles": ", ".join([role.name for role in member.roles]),
                }
                yaml_output_data.append({member.name: data})

        if len(yaml_output_data) == 0:
            await auxiliary.send_deny_embed(
                message=f"No one in this server has the role `{role.name}`",
                channel=ctx.channel,
            )
            return

        # Actually creates the yaml file
        yaml_file = discord.File(
            io.StringIO(yaml.dump(yaml_output_data)),
            filename=f"members-with-{role.name}-in"
            + f"-{ctx.guild.id}-{datetime.datetime.utcnow()}.yaml",
        )

        await ctx.send(file=yaml_file)

    @util.with_typing
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    @commands.command(
        brief="Gets members with role",
        description="Returns all members with a role",
        usage="[role-name]",
    )
    async def members(self, ctx: commands.Context, *, role_name: str):
        """
        Gets members that have a role.

        Args:
            ctx (commands.Context): The context to send the message to
            role_name (str): The role to list the users for
        """
        await self.get_members_with_role(ctx, ctx.guild.members, role_name)
