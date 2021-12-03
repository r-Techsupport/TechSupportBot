import datetime
import json
import uuid

import base
import discord
import util
from discord.ext import commands


def setup(bot):
    config = bot.ExtensionConfig()
    config.add(
        key="webhook_id",
        datatype="str",
        title="Application webhook ID",
        description="The ID of the webhook that posts the application data",
        default=None,
    )
    config.add(
        key="manage_roles",
        datatype="list",
        title="Manage applications roles",
        description="The roles required to manage applications",
        default=["Applications"],
    )
    bot.add_cog(ApplicationManager(bot=bot, extension_name="application"))
    bot.add_extension_config("application", config)


async def has_manage_applications_role(ctx):
    config = await ctx.bot.get_context_config(ctx)
    application_roles = []
    for name in config.extensions.application.manage_roles.value:
        application_role = discord.utils.get(ctx.guild.roles, name=name)
        if not application_role:
            continue
        application_roles.append(application_role)

    if not application_roles:
        raise commands.CommandError("No application management roles found")

    if not any(
        application_role in getattr(ctx.author, "roles", [])
        for role in application_roles
    ):
        raise commands.MissingAnyRole(application_roles)

    return True


class ApplicationEmbed(discord.Embed):
    def __init__(self, *args, **kwargs):
        bot = kwargs.pop("bot")
        super().__init__(*args, **kwargs)
        self.set_author(name="Application Manager", icon_url=bot.user.avatar_url)
        self.color = discord.Color.blurple()


class ApplicationManager(base.MatchCog):

    COLLECTION_NAME = "applications_extension"
    STALE_APPLICATION_DAYS = 30

    async def preconfig(self):
        if not self.COLLECTION_NAME in await self.bot.mongo.list_collection_names():
            await self.bot.mongo.create_collection(self.COLLECTION_NAME)

    async def match(self, config, ctx, content):
        if not ctx.message.webhook_id:
            return False

        if (
            str(ctx.message.webhook_id)
            != config.extensions.application.webhook_id.value
        ):
            return False

        return True

    async def response(self, config, ctx, content, result):
        await ctx.message.delete()

        application_payload = json.loads(ctx.message.content)
        if not application_payload.get("responses"):
            raise ValueError("received empty responses from application webhook")

        user = ctx.guild.get_member_named(application_payload.get("username"))
        if not user:
            raise ValueError("user associated with application could not be found")

        confirmed = await self.confirm_with_user(ctx, user)
        if not confirmed:
            raise RuntimeError(
                "user associated with application has denied making application"
            )

        application_data = {
            "id": str(uuid.uuid4()),
            "responses": application_payload["responses"],
            "user": str(user.id),
            "approved": False,
            "reviewed": False,
            "yayers": [],
            "nayers": [],
            "guild": str(ctx.guild.id),
            "date": str(datetime.datetime.utcnow()),
        }

        embed = self.generate_embed(application_data, new=True)
        await ctx.send(embed=embed)

        collection = self.bot.mongo[self.COLLECTION_NAME]
        await collection.insert_one(application_data)

    async def confirm_with_user(self, ctx, user):
        result = False

        embed = ApplicationEmbed(
            bot=self.bot,
            description=f"I received an application on the server `{ctx.guild.name}`. Did you make this application? Please reply with `yes` or `no`",
        )
        message = await user.send(embed=embed)

        message = await self.bot.wait_for(
            "message",
            check=lambda m: m.content.lower() in ["yes", "no"]
            and m.author.id == user.id
            and isinstance(m.channel, discord.DMChannel),
        )
        if message.content.lower() == "yes":
            result = True

        await message.add_reaction(self.bot.CONFIRM_YES_EMOJI)

        return result

    def generate_embed(self, application_data, new):
        embed = ApplicationEmbed(
            bot=self.bot,
            title="New Application!" if new else "Application Data",
            description=f"Application ID: `{application_data['id']}`",
        )
        for response in application_data["responses"]:
            embed.add_field(
                name=response["question"], value=response["answer"], inline=False
            )

        return embed

    @commands.guild_only()
    @commands.check(has_manage_applications_role)
    @commands.group(
        brief="Executes an application command",
        description="Executes an application command",
    )
    async def application(self, ctx):
        pass

    @application.command(
        name="get",
        brief="Gets an application",
        description="Gets an application by ID",
        usage="[application-id]",
    )
    async def get_application(self, ctx, application_id: str):
        collection = self.bot.mongo[self.COLLECTION_NAME]
        application_data = await collection.find_one({"id": {"$eq": application_id}})
        if not application_data:
            await util.send_with_mention(
                ctx, "I couldn't find an application with that ID"
            )
            return

        embed = self.generate_embed(application_data, new=False)
        await util.send_with_mention(ctx, embed=embed)

    @application.command(
        name="approve",
        brief="Approves an application",
        description="Approves an application by ID",
        usage="[application-id]",
    )
    async def approve_application(self, ctx, application_id: str):
        collection = self.bot.mongo[self.COLLECTION_NAME]
        application_data = await collection.find_one({"id": {"$eq": application_id}})
        if not application_data:
            await util.send_with_mention(
                ctx, "I couldn't find an application with that ID"
            )
            return

        if application_data.get("approved") == True:
            await util.send_with_mention(
                ctx, "That application is already marked as approved"
            )
            return

        application_data["approved"] = True
        await collection.replace_one({"id": application_id}, application_data)

        await self.post_update(ctx, application_data, "approved")

    @application.command(
        name="deny",
        brief="Denies an application",
        description="Denies an application by ID",
        usage="[application-id]",
    )
    async def deny_application(self, ctx, application_id: str):
        collection = self.bot.mongo[self.COLLECTION_NAME]
        application_data = await collection.find_one({"id": {"$eq": application_id}})
        if not application_data:
            await util.send_with_mention(
                ctx, "I couldn't find an application with that ID"
            )
            return

        if application_data.get("approved") == True:
            confirm = await self.bot.confirm(
                ctx,
                "That application has been marked as approved. Are you sure you want to deny it?",
            )
            if not confirm:
                return

        if application_data.get("reviewed") == True:
            await util.send_with_mention(
                ctx, "That application has already been denied"
            )
            return

        application_data["reviewed"] = True
        # set this in case we are denying after approval
        application_data["approved"] = False
        await collection.replace_one({"id": application_id}, application_data)

        try:
            user_id = int(application_data.get("user"))
        except TypeError:
            user_id = None

        await self.post_update(ctx, application_data, "denied")

    async def post_update(self, ctx, application_data, status):
        try:
            user_id = int(application_data.get("user"))
        except TypeError:
            user_id = None

        user = ctx.guild.get_member(user_id)
        message_content = (
            f"I've {status} that application and notified {user}!"
            if user
            else f"I've {status} that application, but could not find the original user"
        )
        await util.send_with_mention(ctx, message_content)

        embed = ApplicationEmbed(
            bot=self.bot,
            title=f"Application {status}!",
            description=f"Hey, your application in `{ctx.guild.name}` has been {status}!",
        )

        if not user:
            return

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass
