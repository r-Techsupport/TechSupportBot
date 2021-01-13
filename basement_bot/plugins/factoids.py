import datetime
import json

from cogs import DatabasePlugin, MatchPlugin
from discord import HTTPException
from discord.ext import commands
from helper import with_typing
from logger import get_logger
from sqlalchemy import Column, DateTime, Integer, String

log = get_logger("Factoids")


class Factoid(DatabasePlugin.BaseTable):
    __tablename__ = "factoids"

    pk = Column(Integer, primary_key=True)
    text = Column(String)
    channel = Column(String)
    message = Column(String)
    time = Column(DateTime, default=datetime.datetime.utcnow)
    embed_config = Column(String, default=None)


def setup(bot):
    bot.add_cog(FactoidManager(bot))


class FactoidManager(DatabasePlugin, MatchPlugin):

    PLUGIN_NAME = __name__
    MODEL = Factoid
    EXAMPLE_JSON = """
    {
        "color": 16747116,
        "author": {
            "name": "Crystal Disk Info",
            "icon_url": "https://cdn.icon-icons.com/icons2/10/PNG/256/savedisk_floppydisk_guardar_1543.png"
        },
        "fields": [
            {
                "name": "1. To check hard drive health, download Crystal Disk Info (CDI):",
                "value": "https://osdn.net/projects/crystaldiskinfo/downloads/73319/CrystalDiskInfo8_7_0.exe"
            },
            {
                "name": "2. At the top of the programs window, copy the contents ",
                "value": "`Edit` -> `Copy`"
            },
            {
                "name": "3. Publish the results in a Pastebin",
                "value": "https://pastebin.com"
            }
        ]
    }"""
    MATCH_PERMISSIONS = ["send_messages"]

    async def db_preconfig(self):
        factoid_prefix = self.config.prefix
        command_prefix = self.bot.config.main.required.command_prefix

        self.bot.plugin_api.plugins.factoids.memory.factoid_events = []

        if factoid_prefix == command_prefix:
            raise RuntimeError(
                f"Command prefix '{command_prefix}' cannot equal Factoid prefix"
            )

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="remember",
        brief="Creates custom trigger with a specified output",
        description=(
            "Creates a custom trigger with a specified name that outputs any specified text,"
            " including mentions. All triggers are used by sending a message with a '?'"
            " appended in front of the trigger name."
        ),
        usage="[trigger-name] [trigger-output]",
        help="Trigger Usage: ?[trigger-name]\n\nLimitations: Mentions should not be used as triggers.",
    )
    async def add_factoid(self, ctx, *args):
        if ctx.message.mentions:
            await self.bot.h.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        embed_config = await self.bot.h.get_json_from_attachment(
            ctx, ctx.message, send_msg_on_none=False, send_msg_on_failure=False
        )
        if embed_config:
            embed_config = json.dumps(embed_config)
        elif embed_config == {}:
            return

        if len(args) >= 2:
            arg1 = args[0]
            args = args[1:]
        else:
            await self.bot.h.tagged_response(ctx, "Invalid input!")
            return

        channel = getattr(ctx.message, "channel", None)
        channel = str(channel.id) if channel else None

        db = self.db_session()

        # first check if key already exists
        entry = db.query(Factoid).filter(Factoid.text == arg1).first()
        if entry:
            # delete old one
            db.delete(entry)
            await self.bot.h.tagged_response(
                ctx, "Deleting previous entry of factoid trigger..."
            )

        # finally, add new entry
        db.add(
            Factoid(
                text=arg1.lower(),
                channel=channel,
                message=" ".join(args),
                embed_config=embed_config,
            )
        )
        db.commit()
        db.close()
        await self.bot.h.tagged_response(
            ctx, f"Successfully added factoid trigger: *{arg1}*"
        )

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="forget",
        brief="Deletes an existing custom trigger",
        description="Deletes an existing custom trigger.",
        usage="[trigger-name]",
        help="\nLimitations: Mentions should not be used as triggers.",
    )
    async def delete_factoid(self, ctx, *args):
        if ctx.message.mentions:
            await self.bot.h.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        if not args:
            await self.bot.h.tagged_response(
                ctx, "You must specify a factoid to delete!"
            )
            return
        else:
            arg = args[0]

        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == arg).first()
        if entry:
            db.delete(entry)
            db.commit()

        db.close()

        await self.bot.h.tagged_response(
            ctx, f"Successfully deleted factoid trigger: *{arg}*"
        )

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        name="lsf",
        brief="List all factoids",
        description="Shows an embed with all the factoids",
        usage="",
        help="\nLimitations: Currently only shows up to 20",
    )
    async def list_all_factoids(self, ctx):
        if ctx.message.mentions:
            await self.bot.h.tagged_response(
                ctx, "Sorry, factoids don't work well with mentions"
            )
            return

        db = self.db_session()

        factoids = (
            db.query(Factoid)
            .filter(bool(Factoid.message) == True)
            .order_by(Factoid.text)
            .all()
        )
        if len(list(factoids)) == 0:
            await self.bot.h.tagged_response(ctx, "No factoids found!")
            return

        field_counter = 1
        embeds = []
        for index, factoid in enumerate(factoids):
            embed = (
                self.bot.embed_api.Embed(
                    title="Factoids",
                    description=f"Access factoids with the `{self.config.prefix}` prefix",
                )
                if field_counter == 1
                else embed
            )
            embed.add_field(
                name=f"{factoid.text} (embed)"
                if factoid.embed_config
                else factoid.text,
                value=factoid.message,
                inline=False,
            )
            if field_counter == self.config.list_all_max or index == len(factoids) - 1:
                embeds.append(embed)
                field_counter = 1
            else:
                field_counter += 1

        db.close()

        self.bot.h.task_paginate(ctx, embeds=embeds, restrict=True)

    async def match(self, _, content):
        return content.startswith(self.config.prefix)

    async def response(self, ctx, arg):
        query = arg[1:]
        user_mentioned = None
        if len(ctx.message.mentions) == 1:
            # tag this user instead of the caller
            user_mentioned = ctx.message.mentions[0]
            query = query.split(" ")[0]
        elif len(ctx.message.mentions) > 1:
            await self.bot.h.tagged_response(
                ctx, "I can only tag one user when referencing a factoid!"
            )
            return

        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == query).first()

        if entry:
            if entry.embed_config:
                embed_config = json.loads(entry.embed_config)
                embed = self.bot.embed_api.Embed.from_dict(embed_config)
                message = None
            else:
                embed = None
                message = entry.message

            message = await self.bot.h.tagged_response(
                ctx, content=message, embed=embed, target=user_mentioned
            )

            if not message:
                await self.bot.h.tagged_response(
                    ctx, "I was unable to render that factoid"
                )
                return

            if not self.bot.plugin_api.plugins.get("relay"):
                return

            # add to the relay plugin queue if it's loaded
            if ctx.channel.id in self.bot.plugin_api.plugins.relay.memory.channels:
                ctx.content = entry.message
                self.bot.plugin_api.plugins.factoids.memory.factoid_events.append(ctx)
                while (
                    len(self.bot.plugin_api.plugins.factoids.memory.factoid_events) > 10
                ):
                    del self.bot.plugin_api.plugins.factoids.memory.factoid_events[0]

        db.close()

    @with_typing
    @commands.has_permissions(send_messages=True)
    @commands.command(
        brief="Gets raw factoid data",
        description="Gets (cats) the raw data of a factoid object",
        usage="[factoid-name]",
        help="\nLimitations: None",
    )
    async def cat(self, ctx, *args):
        if not args:
            await self.bot.h.tagged_response(
                ctx, f"(Example) ```{self.EXAMPLE_JSON}```"
            )
            return

        arg = args[0]

        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == arg).first()

        if not entry:
            await self.bot.h.tagged_response(ctx, "I couldn't find that factoid!")
            return

        # hashtag python
        formatted = (
            json.dumps(json.loads(entry.embed_config), indent=4)
            if entry.embed_config
            else entry.message
        )

        db.close()

        await self.bot.h.tagged_response(ctx, f"```{formatted}```")
