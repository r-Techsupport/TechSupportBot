"""
Name: Embed
Info: Converts an attached .json file to an embed
Unit tests: None
Config: embed_roles
API: None
Databases: None 
Models: None
Subcommands: embed 
Defines: has_embed_role
"""
import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
    """Registers the extension and its config"""
    config = bot.ExtensionConfig()
    config.add(
        key="embed_roles",
        datatype="list",
        title="Allowed embed roles",
        description="The list of role names able to use the embed commands",
        default=[],
    )
    await bot.add_cog(Embedder(bot=bot))
    bot.add_extension_config("embed", config)


async def has_embed_role(ctx: commands.Context) -> bool:
    """--COMAND CHECK--
    Checks if the invoker has an embed role (is allowed to use .embed)

    Args:
        ctx (commands.Context): Context of the invokation

    Raises:
        commands.CommandError: Raised if embed_roles isn't set up
        commands.MissingAnyRole: Raised if the invoker is missing a role

    Returns:
        bool: Whether the invoker has the role
    """
    config = await ctx.bot.get_context_config(ctx)
    embed_roles = []
    # Gets the embed roles from the config if they exist
    for name in config.extensions.embed.embed_roles.value:
        embed_role = discord.utils.get(ctx.guild.roles, name=name)
        if not embed_role:
            continue
        embed_roles.append(embed_role)

    # If they don't exist
    if not embed_roles:
        raise commands.CommandError("There aren't any `embed_roles` set in the config!")

    # Checking against the user to see if they have the roles specified in the config
    if not any(
        embed_role in getattr(ctx.author, "roles", []) for embed_role in embed_roles
    ):
        raise commands.MissingAnyRole(embed_roles)

    # Invoker has an embed_role
    return True


class Embedder(base.BaseCog):
    """Main extension class"""

    @util.with_typing
    @commands.has_permissions(manage_messages=True)
    @commands.check(has_embed_role)
    @commands.command(
        brief="Generates a list of embeds",
        description="Generates a list of embeds defined by an uploaded JSON file "
        + "(see: https://discord.com/developers/docs/resources/channel#embed-object)",
        usage="[keep-succesful-if-one-fails] |embed-list-json-upload|",
    )
    async def embed(self, ctx: commands.Context, *, keep_option: str = None):
        """Command to convert an attached .json to an embed

        Args:
            ctx (commands.Context): Context of the invokation
            keep_option (str, optional): Whether to keep succesful embeds if one fails
                                         Defaults to None.
        """
        # -> Message checks <-

        # If files weren't supplied, if not only JSONs were supplied
        if not ctx.message.attachments or not any(
            [
                attachment.filename.endswith(".json")
                for attachment in ctx.message.attachments
            ]
        ):
            await auxiliary.send_deny_embed(
                message="Please provide JSON files for your embeds",
                channel=ctx.channel,
            )
            return

        # Gets the embeds from the attached file
        request_body = await util.get_json_from_attachments(ctx.message)

        # If the data wasn't succesfully gained
        if not request_body:
            await auxiliary.send_deny_embed(
                message="I couldn't find any data in your upload", channel=ctx.channel
            )
            return

        # Gets discord.Embed objects from the json
        embeds = await self.process_request(request_body)

        # If no embeds were succesfully gained
        if not embeds:
            await auxiliary.send_deny_embed(
                message="I was unable to generate any embeds from your request",
                channel=ctx.channel,
            )
            return

        # -> Sending the embeds <-

        sent_messages = []  # Used it the keep flag wasn't supplied
        delete = False  # Used to delete all embeds if one failed

        # Sends all embeds
        for embed in embeds:
            try:
                sent_message = await ctx.send(embed=embed)
                sent_messages.append(sent_message)

            # If an embed wasn't formed properly
            except discord.errors.HTTPException:
                delete = True

        if delete:
            if keep_option.lower() in ["keep", "true"]:
                await ctx.author.send("I couldn't generate all of your embeds")
                return

            # Deletes all embeds to clean up
            for message in sent_messages:
                await message.delete()

            await ctx.author.send(
                "I couldn't generate all of your embeds, so I gave you a blank slate",
            )

    async def process_request(self, request_body) -> list[discord.Embed]:
        """Returns a list of discord.Embed objects from a request_body

        Args:
            request_body (munch.Munch): Embed json list

        Returns:
            list[discord.Embed]: List containing discord.Embed objects
        """
        embeds = []
        # Iterates through all embeds and appends them to embeds
        for embed_request in request_body.get("embeds", []):
            embeds.append(discord.Embed.from_dict(embed_request))

        return embeds
