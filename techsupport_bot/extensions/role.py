import base
import discord
import ui
from discord import app_commands


async def setup(bot):
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
        title="The list of roles allowed to use /role self",
        description="The list of roles that are allowed to assign themselves roles",
        default=[],
    )
    await bot.add_cog(RoleGiver(bot=bot))
    bot.add_extension_config("role", config)


class RoleGiver(base.BaseCog):
    group = app_commands.Group(name="role", description="...")

    @group.command(name="self")
    async def self_role(self, interaction):
        #config = await ctx.bot.get_context_config(ctx)
        roles = ["Trusted", "Helper", "bots", "dev", "asdf"]
        role_options = self.generate_options(interaction.user, interaction.guild, roles)
        view = ui.SelectView(role_options)
        await interaction.response.send_message(
            "Hello from two", ephemeral=True, view=view
        )
        await view.wait()
        await interaction.channel.send(content=view.select.values)

    def generate_options(self, user, guild, roles):
        options = []

        default = False

        for role_name in roles:
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
