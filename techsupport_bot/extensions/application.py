"""Module for defining the application bot methods."""
import datetime
import io
import json
import uuid

import aiocron
import base
import discord
import embeds
import munch
import yaml
from discord.ext import commands


async def setup(bot):
    """
    Method to setup the bot, and configure different management role config options for
    the promotion application framework.
    """
    # For the webhook id to add to discord
    config = bot.ExtensionConfig()
    config.add(
        key="webhook_id",
        datatype="str",
        title="Application webhook ID",
        description="The ID of the webhook that posts the application data",
        default=None,
    )
    # To configure the roles that can manage the applications
    config.add(
        key="manage_roles",
        datatype="list",
        title="Manage applications roles",
        description="The list of roles required to manage applications",
        default=["Applications"],
    )
    # To ping roles when an application is recieved
    config.add(
        key="ping_roles",
        datatype="list",
        title="New application ping roles",
        description="The list of roles that are pinged on new applications",
        default=["Applications"],
    )
    # for a reminder on recieved applications
    config.add(
        key="reminder_on",
        datatype="bool",
        title="Reminder feature toggle",
        description="True if the bot should periodically remind of pending applications",
        default=False,
    )
    # The syntax for how reminders should work
    config.add(
        key="reminder_cron_config",
        datatype="string",
        title="Application reminder cron config",
        description="The cron syntax for automatic application reminders",
        default="0 17 * * *",
    )
    # The list of approved roles to give when an apllication is approved
    config.add(
        key="approve_roles",
        datatype="list",
        title="Approved application roles",
        description="The list of role names to give someone once they are approved",
        default=[],
    )
    await bot.add_cog(ApplicationManager(bot=bot, extension_name="application"))
    bot.add_extension_config("application", config)


async def has_manage_applications_role(ctx):
    """Method to define who has mangagment roles"""
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
    """Class to change the color and title of the embed to discord."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "Application Manager"
        self.color = discord.Color.blurple()


class NoPendingApplications(Exception):
    """Class for what happens when no applications are recieved."""

    pass


class ApplicationManager(base.MatchCog, base.LoopCog):
    """Class to manage the application extension of the bot, including getting data and status."""

    COLLECTION_NAME = "applications_extension"
    STALE_APPLICATION_DAYS = 30
    MAX_REMINDER_FIELDS = 10

    async def preconfig(self):
        """Method to run on first time, used to create mongo collections"""
        if not self.COLLECTION_NAME in await self.bot.mongo.list_collection_names():
            await self.bot.mongo.create_collection(self.COLLECTION_NAME)

    async def match(self, config, ctx, content):
        """Method to match webhook id."""
        if not ctx.message.webhook_id:
            return False

        if (
            str(ctx.message.webhook_id)
            != config.extensions.application.webhook_id.value
        ):
            return False

        return True

    async def response(self, config, ctx, content, result):
        """Method to handle the response of an application."""
        await ctx.message.delete()

        application_payload = json.loads(ctx.message.content)
        if not application_payload.get("responses"):
            raise ValueError("received empty responses from application webhook")

        username = application_payload.get("username")
        user = ctx.guild.get_member_named(username)
        if not user:
            return await self.handle_error_embed(
                ctx, f"Could not find {username} in server - ignoring application"
            )

        try:
            confirmed = await self.confirm_with_user(ctx, user)
        except discord.Forbidden:
            return await self.handle_error_embed(
                ctx,
                f"Could not confirm application: {user} has direct messages blocked",
            )

        if not confirmed:
            return await self.handle_error_embed(
                ctx, f"{user} has denied making application"
            )

        application_data = {
            "id": str(uuid.uuid4()),
            "responses": application_payload["responses"],
            "user_id": str(user.id),
            "username": str(user),
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
            mention_author=False,
        )

        collection = self.bot.mongo[self.COLLECTION_NAME]
        await collection.insert_one(application_data)
        # For handeling a connection to IRC in the applcation channel
        self.bot.dispatch(
            "extension_listener_event", munch.Munch(channel=ctx.channel, embed=embed)
        )

    async def handle_error_embed(self, ctx, message_send):
        """Method to handle if an application recieved an error."""
        embed_send = embeds.DenyEmbed(message=message_send)
        await ctx.channel.send(content="", embed=embed_send)
        # For handeling a connection to IRC in the applcation channel
        self.bot.dispatch(
            "extension_listener_event",
            munch.Munch(channel=ctx.channel, embed=embed_send),
        )

    async def execute(self, config, guild):
        """Method to excute the reminder for pending applications."""
        if not config.extensions.application.reminder_on.value:
            return

        try:
            await self.send_reminder(config, guild)
        except NoPendingApplications:
            pass

    async def wait(self, config, _):
        """Method to get wait value for the reminder."""
        await aiocron.crontab(
            config.extensions.application.reminder_cron_config.value
        ).next()

    async def send_reminder(self, config, guild, automated=True):
        """Method to send the reminder to discord."""
        try:
            webhook_id = int(config.extensions.application.webhook_id.value)
        except TypeError as exc:
            raise ValueError("applications webhook ID not found in config") from exc

        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
        except discord.NotFound as exc:
            raise RuntimeError(
                "application webhook not found from configured ID"
            ) from exc

        applications = await self.get_applications(guild, status="pending")
        if not applications:
            raise NoPendingApplications()

        embed = ApplicationEmbed()
        embed.set_footer(
            text="This is a periodic reminder"
            if automated
            else "This reminder was triggered manually"
        )

        for app in applications:
            # remove this until voting implemented
            app = self.clean_file_data(app)

            if len(embed.fields) < self.MAX_REMINDER_FIELDS:
                id = app.get("id")
                if not id:
                    continue
                username = app.get("username")
                if not username:
                    continue
                embed.add_field(name=username, value=id, inline=False)

        description = f"Pending applications: {len(applications)}"
        remaining = (
            (len(applications) - len(embed.fields)) if len(embed.fields) != 0 else 0
        )

        file = None
        if remaining > 0:
            description = f"{description} - see attached for all applications"
            file = discord.File(
                io.StringIO(yaml.dump(applications)),
                filename=f"pending-apps-for-server-{guild.id}-{datetime.datetime.utcnow()}.yaml",
            )

        embed.description = description

        mention_string = await self.get_mention_string(guild)
        await webhook.channel.send(
            content=mention_string,
            embed=embed,
            file=file,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    @staticmethod
    def clean_file_data(application_data):
        """Method to delete db data after an application."""
        try:
            del application_data["_id"]
            del application_data["yayers"]
            del application_data["nayers"]
        except KeyError:
            pass
        return application_data

    async def get_applications(
        self, guild, status=None, include_stale=False, limit=100
    ):
        """Method to review applications that have been recieved."""
        returned_applications = []

        query = {"guild": {"$eq": str(guild.id)}}

        status = status.lower() if status else None
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
            returned_applications = applications
        else:
            for application_data in applications:
                now = datetime.datetime.utcnow()
                application_date = application_data.get("date", str(now))
                try:
                    age = now - datetime.datetime.fromisoformat(application_date)
                except ValueError:
                    age = datetime.timedelta(0)
                if (age).seconds / 86400 > self.STALE_APPLICATION_DAYS:
                    continue
                returned_applications.append(application_data)

        return returned_applications

    async def confirm_with_user(self, ctx, user):
        """Method to confirm application with the user through direct message."""
        embed = ApplicationEmbed(
            description=f"I received an application on the server `{ctx.guild.name}`. \
                Did you make this application? Please reply with `yes` or `no`",
        )
        message = await user.send(embed=embed)

        message = await self.bot.wait_for(
            "message",
            check=lambda m: m.content.lower() in ["yes", "no"]
            and m.author.id == user.id
            and isinstance(m.channel, discord.DMChannel),
        )
        await message.add_reaction(ctx.CONFIRM_YES_EMOJI)
        return message.content.lower() == "yes"

    @staticmethod
    def determine_app_status(application_data, lower=False):
        """Method to determine the current application status (approved or denied)"""
        approved = application_data.get("approved", False)
        reviewed = application_data.get("reviewed", False)
        status = "Pending"
        if approved:
            status = "Approved"
        elif reviewed:
            status = "Denied"
        return status.lower() if lower else status

    def generate_embed(self, application_data, new):
        """Method to generate the embed to send to discord."""
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
        """Method to get the mention string."""
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
        """Method for application."""

        # Executed if there are no/invalid args supplied
        await base.extension_help(self, ctx, self.__module__[11:])

        pass

    @application.command(
        name="get",
        brief="Gets an application",
        description="Gets an application by ID",
        usage="[application-id]",
    )
    async def get_app(self, ctx, application_id: str):
        """Method to fetch application by ID"""
        collection = self.bot.mongo[self.COLLECTION_NAME]
        application_data = await collection.find_one({"id": {"$eq": application_id}})
        if not application_data:
            await ctx.send_deny_embed("I couldn't find an application with that ID")
            return

        embed = self.generate_embed(application_data, new=False)
        await ctx.send(embed=embed)

    @application.command(
        name="all",
        brief="Gets all applications",
        description="Gets all applications given an optional status",
        usage="[status (optional: approved/denied/pending)]",
    )
    async def get_all_apps(self, ctx, status: str = None):
        """Method to pull all the applications pending."""
        applications = await self.get_applications(
            ctx.guild, status=status, include_stale=True
        )
        if not applications:
            await ctx.send_deny_embed("I couldn't find any applications")
            return

        for app in applications:
            # remove this from the surface until voting implemented
            app = self.clean_file_data(app)

        yaml_file = discord.File(
            io.StringIO(yaml.dump(applications)),
            filename=f"applications-for-server-{ctx.guild.id}-{datetime.datetime.utcnow()}.yaml",
        )
        await ctx.send(file=yaml_file)

    @application.command(
        name="approve",
        brief="Approves an application",
        description="Approves an application by ID",
        usage="[application-id]",
    )
    async def approve_application(self, ctx, application_id: str):
        """Method to approve the application and assign the role."""
        collection = self.bot.mongo[self.COLLECTION_NAME]
        application_data = await collection.find_one({"id": {"$eq": application_id}})
        if not application_data:
            await ctx.send_deny_embed("I couldn't find an application with that ID")
            return

        status = self.determine_app_status(application_data, lower=True)

        if status == "approved":
            await ctx.send_deny_embed("That application is already marked as approved")
            return

        if status == "denied":
            confirm = await ctx.confirm(
                "That application has been marked as denied. Are you sure you want to approve it?",
            )
            if not confirm:
                await ctx.send_deny_embed("Application was not approved")
                return

        username = application_data.get("username", "the user")
        confirm = await ctx.confirm(
            f"This will attempt to notify `{username}` and approve their application",
        )
        if not confirm:
            await ctx.send_deny_embed(
                f"The application was not approved and `{username}` was not notified"
            )
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
        """Method to deny the application with reason to why."""
        collection = self.bot.mongo[self.COLLECTION_NAME]
        application_data = await collection.find_one({"id": {"$eq": application_id}})
        if not application_data:
            await ctx.send_deny_embed("I couldn't find an application with that ID")
            return

        status = self.determine_app_status(application_data, lower=True)

        if status == "denied":
            await ctx.send_deny_embed("That application is already marked as denied")
            return

        if status == "approved":
            confirm = await ctx.confirm(
                "That application has been marked as approved. Are you sure you want to deny it?",
            )
            if not confirm:
                await ctx.send_deny_embed("Application was not denied")
                return

        username = application_data.get("username", "the user")
        confirm = await ctx.confirm(
            f"This will attempt to notify `{username}` and deny their application",
        )
        if not confirm:
            await ctx.send_deny_embed(
                f"The application was not denied and `{username}` was not notified"
            )
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
        """Method for reminding the configured role about pending applications"""
        config = await self.bot.get_context_config(ctx)
        try:
            await self.send_reminder(config, ctx.guild, automated=False)
        except NoPendingApplications:
            await ctx.send_deny_embed("There are no pending applications")

    async def post_update(self, ctx, application_data, status, reason=None):
        """Method to update the application after approving or denying."""
        status = status.lower()
        if status not in ["approved", "denied"]:
            raise RuntimeError(
                f"invalid application status: {status} passed to post-update handler"
            )

        try:
            user_id = int(application_data.get("user_id"))
        except TypeError:
            user_id = None

        user = ctx.guild.get_member(user_id)
        message_content = (
            f"I've {status} that application and notified `{user}`!"
            if user
            else f"I've {status} that application, but the applicant has left the server"
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
