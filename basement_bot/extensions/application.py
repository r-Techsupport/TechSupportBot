import datetime
import json
import uuid
from typing import Type

import aiocron
import base
import discord
import util
import yaml
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
        description="The list of roles required to manage applications",
        default=["Applications"],
    )
    config.add(
        key="ping_roles",
        datatype="list",
        title="New application ping roles",
        description="The list of roles that are pinged on new applications",
        default=["Applications"],
    )
    config.add(
        key="reminder_on",
        datatype="bool",
        title="Reminder feature toggle",
        description="True if the bot should periodically remind of pending applications",
        default=False,
    )
    config.add(
        key="reminder_cron_config",
        datatype="string",
        title="Application reminder cron config",
        description="The cron syntax for automatic application reminders",
        default="0 17 * * *",
    )
    config.add(
        key="approve_roles",
        datatype="list",
        title="Approved application roles",
        description="The list of role names to give someone once they are approved",
        default=[],
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
        for application_role in application_roles
    ):
        raise commands.MissingAnyRole(application_roles)

    return True


class ApplicationEmbed(discord.Embed):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "Application Manager"
        self.color = discord.Color.blurple()


class NoPendingApplications(Exception):
    pass


class ApplicationManager(base.MatchCog, base.LoopCog):

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

        mention_string = await self.get_mention_string(ctx.guild)
        await ctx.send(
            content=mention_string,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        collection = self.bot.mongo[self.COLLECTION_NAME]
        await collection.insert_one(application_data)

    async def execute(self, config, guild):
        if not config.extensions.application.reminder_on.value:
            return

        try:
            await self.send_reminder(config, guild)
        except NoPendingApplications:
            pass

    async def wait(self, config, _):
        await aiocron.crontab(
            config.extensions.application.reminder_cron_config.value
        ).next()

    async def send_reminder(self, config, guild, automated=True):
        try:
            webhook_id = int(config.extensions.application.webhook_id.value)
        except TypeError:
            raise ValueError("applications webhook ID not found in config")

        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
        except discord.NotFound:
            raise RuntimeError("application webhook not found from configured ID")

        applications = await self.get_applications(guild, status="pending")
        if not applications:
            raise NoPendingApplications()

        embed = ApplicationEmbed()
        embed.set_footer(
            text="This is a periodic reminder"
            if automated
            else "This reminder was triggered manually"
        )

        fields = 0
        for app in applications:
            if fields >= 5:
                break

            id = app.get("id")
            if not id:
                continue
            try:
                user_id = int(app.get("user"))
            except TypeError:
                user_id = 0
            user = guild.get_member(user_id)
            if not user:
                continue

            embed.add_field(name=user, value=id, inline=False)
            fields += 1

        description = f"Pending applications: {len(applications)}"
        remaining = len(applications) - fields
        if remaining > 0:
            description = f"{description} - please review the following ID's and use the reminder command to view more"
        embed.description = description

        mention_string = await self.get_mention_string(guild)
        await webhook.channel.send(
            content=mention_string,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    async def get_applications(
        self, guild, status=None, include_stale=False, limit=100
    ):
        returned_applications = []

        query = {"guild": {"$eq": str(guild.id)}}

        status = status.lower()
        if status and not status in ["pending", "approved", "denied"]:
            raise ValueError("status must be one of: pending, approved, denied")

        if status == "pending":
            query["reviewed"] = {"$eq": False}
            query["approved"] = {"$eq": False}
        elif status == "denied":
            query["reviewed"] = {"$eq": True}
            query["approved"] = {"$eq": False}
        elif status == "approved":
            query["reviewed"] = {"$eq": True}
            query["approved"] = {"$eq": True}

        applications = []
        cursor = self.bot.mongo[self.COLLECTION_NAME].find(query)
        for document in await cursor.to_list(length=limit):
            applications.append(document)
        if not applications:
            return returned_applications

        if include_stale:
            return returned_applications

        for application_data in applications:
            now = datetime.datetime.utcnow()
            application_date = application_data.get("date", str(now))
            try:
                age = now - datetime.datetime.fromisoformat(application_date)
            except Exception:
                age = datetime.timedelta(0)
            if (age).seconds / 86400 > self.STALE_APPLICATION_DAYS:
                continue
            returned_applications.append(application_data)

        return returned_applications

    async def confirm_with_user(self, ctx, user):
        result = False

        embed = ApplicationEmbed(
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

    @staticmethod
    def determine_app_status(application_data):
        approved = application_data.get("approved", False)
        reviewed = application_data.get("reviewed", False)
        status = "Pending"
        if approved:
            status = "Approved"
        elif reviewed:
            status = "Denied"
        return status

    def generate_embed(self, application_data, new):
        embed = ApplicationEmbed(
            description=("New Application! " if new else "")
            + f"Application ID: `{application_data['id']}`",
        )
        for response in application_data["responses"]:
            embed.add_field(
                name=response["question"], value=response["answer"], inline=False
            )

        embed.set_footer(text=f"Status: {self.determine_app_status(application_data)}")

        return embed

    async def get_mention_string(self, guild):
        config = await self.bot.get_context_config(guild=guild)
        mention_string = ""
        for index, role_name in enumerate(
            config.extensions.application.ping_roles.value
        ):
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                continue
            mention_string += role.mention + (
                " "
                if index != len(config.extensions.application.ping_roles.value) - 1
                else ""
            )
        return mention_string

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
    async def get_application_by_id(self, ctx, application_id: str):
        collection = self.bot.mongo[self.COLLECTION_NAME]
        application_data = await collection.find_one({"id": {"$eq": application_id}})
        if not application_data:
            await ctx.send_deny_embed("I couldn't find an application with that ID")
            return

        embed = self.generate_embed(application_data, new=False)
        await ctx.send(embed=embed)

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
            await ctx.send_deny_embed("I couldn't find an application with that ID")
            return

        if application_data.get("approved") == True:
            await ctx.send_deny_embed("That application is already marked as approved")
            return

        confirmed = await self.bot.confirm(
            ctx,
            "This will notify the user and approve their application. Are you sure?",
        )
        if not confirmed:
            return

        application_data["approved"] = True
        application_data["reviewed"] = True
        await collection.replace_one({"id": application_id}, application_data)

        await self.post_update(ctx, application_data, "approved")

    @application.command(
        name="deny",
        brief="Denies an application",
        description="Denies an application by ID",
        usage="[application-id] [reason]",
    )
    async def deny_application(self, ctx, application_id: str, *, reason: str = None):
        collection = self.bot.mongo[self.COLLECTION_NAME]
        application_data = await collection.find_one({"id": {"$eq": application_id}})
        if not application_data:
            await ctx.send_deny_embed("I couldn't find an application with that ID")
            return

        if application_data.get("approved") == True:
            confirm = await self.bot.confirm(
                ctx,
                "That application has been marked as approved. Are you sure you want to deny it?",
            )
            if not confirm:
                return

        confirmed = await self.bot.confirm(
            ctx, "This will notify the user and deny their application. Are you sure?"
        )
        if not confirmed:
            return

        application_data["reviewed"] = True
        # set this in case we are denying after approval
        application_data["approved"] = False
        await collection.replace_one({"id": application_id}, application_data)

        await self.post_update(ctx, application_data, "denied", reason)

    @application.command(
        name="remind",
        brief="Sends an application reminder",
        description="Sends an application reminder to the configured channel",
    )
    async def remind(self, ctx):
        config = await self.bot.get_context_config(ctx)
        try:
            await self.send_reminder(config, ctx.guild, automated=False)
        except NoPendingApplications:
            await ctx.send_deny_embed("There are no pending applications")

    async def post_update(self, ctx, application_data, status, reason=None):
        status = status.lower()
        if status not in ["approved", "denied"]:
            raise RuntimeError(
                f"invalid application status: {status} passed to post-update handler"
            )

        try:
            user_id = int(application_data.get("user"))
        except TypeError:
            user_id = None

        user = ctx.guild.get_member(user_id)
        message_content = (
            f"I've {status} that application and notified `{user}`!"
            if user
            else f"I've {status} that application, but could not find the original user"
        )
        await ctx.send_confirm_embed(message_content)

        embed = ApplicationEmbed(
            description=f"Hey, your application in `{ctx.guild.name}` has been {status}!",
        )
        if reason:
            embed.description = f"{embed.description} Reason: {reason}"

        if not user:
            return

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass

        if status == "approved":
            config = await self.bot.get_context_config(ctx)
            roles = []
            for role_name in config.extensions.application.approve_roles.value:
                role = discord.utils.get(ctx.guild.roles, name=role_name)
                if not role:
                    continue
                roles.append(role)

            await user.add_roles(*roles)
