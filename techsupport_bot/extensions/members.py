"""
Module for searching members by a role. 
This is inefficient, awful, stinky, memory consuming, but it is an issue and might as well make it.
"""
import datetime
import io
import yaml

import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Method to add the member command to config."""
    await bot.add_cog(Members(bot=bot))


class Members(base.BaseCog):
    """Class for the Member command on the discord bot."""

    async def Get_members_with_role(
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

        # Checks if role actually exists
        if role_name not in [role.name for role in ctx.guild.roles]:
            await ctx.send_deny_embed(f"I couldn't find the role `{role_name}`")
            return

        # Iterates through members, appends their info to a yaml file
        output_data = []
        for member in member_list:
            if role_name in [role.name for role in member.roles]:
                data = {
                    "id": member.id,
                    "roles": ", ".join([role.name for role in member.roles]),
                }
                output_data.append({member.name: data})

        if len(output_data) == 0:
            await ctx.send_deny_embed(
                f"Noone in this server has the role `{role_name}`"
            )
            return

        # Actually creates the yaml file
        yaml_file = discord.File(
            io.StringIO(yaml.dump(output_data)),
            filename=f"members-with-{role_name}-in-{ctx.guild.id}-{datetime.datetime.utcnow()}.yaml",
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
        Gets members that habe a role.

        Args:
            ctx (commands.Context): The context to send the message to
            role_name (str): The role to list the users for
        """
        await self.Get_members_with_role(ctx, ctx.guild.members, role_name)
