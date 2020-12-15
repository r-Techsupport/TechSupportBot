import datetime
import json

from cogs import DatabasePlugin, MatchPlugin
from discord import HTTPException
from discord.ext import commands
from sqlalchemy import Column, DateTime, Integer, String
from utils.embed import SafeEmbed
from utils.helpers import *
from utils.logger import get_logger

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

    async def db_preconfig(self):
        factoid_prefix = self.config.prefix
        command_prefix = self.bot.config.main.required.command_prefix

        self.bot.plugin_api.plugins.factoids.memory.factoid_events = []

        if factoid_prefix == command_prefix:
            raise RuntimeError(
                f"Command prefix '{command_prefix}' cannot equal Factoid prefix"
            )

    @commands.check(is_admin)
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
            await priv_response(ctx, "Sorry, factoids don't work well with mentions")
            return

        embed_config = await get_json_from_attachment(
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
            await priv_response(ctx, "Invalid input!")
            return

        channel = getattr(ctx.message, "channel", None)
        channel = str(channel.id) if channel else None

        db = self.db_session()

        # first check if key already exists
        entry = db.query(Factoid).filter(Factoid.text == arg1).first()
        if entry:
            # delete old one
            db.delete(entry)
            await priv_response(ctx, "Deleting previous entry of factoid trigger...")

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
        await tagged_response(ctx, f"Successfully added factoid trigger: *{arg1}*")

    @commands.check(is_admin)
    @commands.command(
        name="forget",
        brief="Deletes an existing custom trigger",
        description="Deletes an existing custom trigger.",
        usage="[trigger-name]",
        help="\nLimitations: Mentions should not be used as triggers.",
    )
    async def delete_factoid(self, ctx, *args):
        if ctx.message.mentions:
            await priv_response(ctx, "Sorry, factoids don't work well with mentions")
            return

        if not args:
            await priv_response(ctx, "You must specify a factoid to delete!")
            return
        else:
            arg = args[0]

        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == arg).first()
        if entry:
            db.delete(entry)
            db.commit()

        db.close()

        await tagged_response(ctx, f"Successfully deleted factoid trigger: *{arg}*")

    @commands.command(
        name=f"lsf",
        brief="List all factoids",
        description="Shows an embed with all the factoids",
        usage="",
        help="\nLimitations: Currently only shows up to 20",
    )
    async def list_all_factoids(self, ctx):
        if ctx.message.mentions:
            await priv_response(ctx, "Sorry, factoids don't work well with mentions")
            return

        db = self.db_session()

        factoids = db.query(Factoid).filter(bool(Factoid.message) == True).all()
        if len(list(factoids)) == 0:
            await priv_response(ctx, "No factoids found!")
            return

        field_counter = 1
        embeds = []
        for index, factoid in enumerate(factoids):
            embed = (
                SafeEmbed(
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

        await paginate(ctx, embeds=embeds, restrict=True)

    def match(self, ctx, content):
        return content.startswith(self.config.prefix)

    async def response(self, ctx, arg):
        query = arg[1:]
        user_mentioned = None
        if len(ctx.message.mentions) == 1:
            # tag this user instead of the caller
            user_mentioned = ctx.message.mentions[0]
            query = query.split(" ")[0]
        elif len(ctx.message.mentions) > 1:
            await priv_response(
                ctx, "I can only tag one user when referencing a factoid!"
            )
            return

        db = self.db_session()

        entry = db.query(Factoid).filter(Factoid.text == query).first()

        if entry:
            if entry.embed_config:
                embed_config = json.loads(entry.embed_config)
                embed = Embed.from_dict(embed_config)
                message = None
            else:
                embed = None
                message = entry.message

            await tagged_response(
                ctx, content=message, embed=embed, target=user_mentioned
            )

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
