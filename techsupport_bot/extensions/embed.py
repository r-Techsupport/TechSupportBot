import base
import discord
import util
from base import auxiliary
from discord.ext import commands


async def setup(bot):
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


async def has_embed_role(ctx):
    """
    Check if the user is allowed to run embed commands or not
    """
    config = await ctx.bot.get_context_config(ctx)
    embed_roles = []
    for name in config.extensions.embed.embed_roles.value:
        embed_role = discord.utils.get(ctx.guild.roles, name=name)
        if not embed_role:
            continue
        embed_roles.append(embed_role)

    if not embed_roles:
        raise commands.CommandError("no embed management roles found")
    # Checking against the user to see if they have the roles specified in the config
    if not any(
        embed_role in getattr(ctx.author, "roles", []) for embed_role in embed_roles
    ):
        raise commands.MissingAnyRole(embed_roles)

    return True


class Embedder(base.BaseCog):
    @util.with_typing
    @commands.has_permissions(manage_messages=True)
    @commands.check(has_embed_role)
    @commands.command(
        brief="Generates a list of embeds",
        description="Generates a list of embeds defined by an uploaded JSON file (see: https://discord.com/developers/docs/resources/channel#embed-object)",
        usage="|embed-list-json-upload|",
    )
    async def embed(self, ctx, *, keep_option: str = None):
        if not ctx.message.attachments:
            await auxiliary.send_deny_embed(
                message="Please provide a JSON file for your embeds",
                channel=ctx.channel,
            )
            return

        request_body = await util.get_json_from_attachments(ctx.message)
        if not request_body:
            await auxiliary.send_deny_embed(
                message="I couldn't find any data in your upload", channel=ctx.channel
            )
            return

        embeds = await self.process_request(ctx, request_body)
        if not embeds:
            await auxiliary.send_deny_embed(
                message="I was unable to generate any embeds from your request",
                channel=ctx.channel,
            )
            return

        sent_messages = []
        delete = False
        for embed in embeds:
            try:
                # in theory this could spam the API?
                sent_message = await ctx.send(embed=embed)
                sent_messages.append(sent_message)
            except Exception:
                delete = True

        if delete:
            if keep_option == "keep":
                await ctx.author.send("I couldn't generate all of your embeds")
                return

            for message in sent_messages:
                await message.delete()

            await ctx.author.send(
                "I couldn't generate all of your embeds, so I gave you a blank slate",
            )

    async def process_request(self, ctx, request_body):
        embeds = []
        try:
            for embed_request in request_body.get("embeds", []):
                embeds.append(discord.Embed.from_dict(embed_request))
        except Exception:
            pass

        return embeds
