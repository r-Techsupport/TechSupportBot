import datetime
import json

from cogs import DatabasePlugin, MatchPlugin
from discord import Embed, HTTPException
from discord.ext import commands
from sqlalchemy import Column, DateTime, Integer, String
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
    bot.add_cog(FactoidManager(bot, Factoid))


class FactoidManager(DatabasePlugin, MatchPlugin):
    PLUGIN_NAME = __name__

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
            ctx, ctx.message, send_msg_on_error=False
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

        try:
            # first check if key already exists
            entry = db.query(Factoid).filter(Factoid.text == arg1).first()
            if entry:
                # delete old one
                db.delete(entry)
                await priv_response(
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
            await tagged_response(ctx, f"Successfully added factoid trigger: *{arg1}*")

        except Exception as e:
            log.warning(f"Unable to add factoid: {e}")
            await priv_response(
                ctx, "I ran into an issue handling your factoid addition..."
            )

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

        try:
            entry = db.query(Factoid).filter(Factoid.text == arg).first()
            if entry:
                db.delete(entry)
                db.commit()
            await tagged_response(ctx, f"Successfully deleted factoid trigger: *{arg}*")

        except Exception as e:
            log.warning(f"Unable to forget factoid: {e}")
            await priv_response(
                ctx, "I ran into an issue handling your factoid deletion..."
            )

    @commands.check(is_admin)
    @commands.command(
        name=f"cat",
        brief="List all factoids",
        description="Shows an embed with all the factoids",
        usage="",
        help="\nLimitations: Currently only shows up to 20",
    )
    async def cat_factoid(self, ctx, *args):
        if ctx.message.mentions:
            await priv_response(ctx, "Sorry, factoids don't work well with mentions")
            return

        if not args:
            await priv_response(ctx, "You must specify a factoid to delete!")
            return
        else:
            arg = args[0]

        db = self.db_session()

        try:
            entry = db.query(Factoid).filter(Factoid.text == arg).first()
            if entry:
                if entry.embed_config:
                    try:
                        message = json.dumps(json.loads(entry.embed_config), indent=2)
                    except Exception:
                        await priv_response(
                            ctx, "I was unable to parse the JSON for that factoid!"
                        )
                        return
                else:
                    message = entry.message

                await tagged_response(ctx, f"```{message}```")

        except Exception as e:
            log.warning(f"Unable to get factoid: {e}")
            await priv_response(ctx, "I ran into an issue catting your factoid info...")

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

        try:
            factoids = db.query(Factoid).filter(bool(Factoid.message) == True).all()
        except Exception:
            await priv_response(ctx, "I was unable to get all the factoids...")
            return
        if len(list(factoids)) == 0:
            await priv_response(ctx, "No factoids found!")
            return

        field_counter = 1
        embeds = []
        for index, factoid in enumerate(factoids):
            embed = (
                Embed(
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

        await paginate(ctx, embeds=embeds, restrict=True)

    def match(self, _, content):
        return bool(content.startswith(self.config.prefix))

    async def response(self, ctx, arg):
        if ctx.message.mentions:
            await priv_response(ctx, "Sorry, factoids don't work well with mentions")
            return

        db = self.db_session()

        try:
            entry = db.query(Factoid).filter(Factoid.text == arg[1:]).first()
            if entry:
                if entry.embed_config:
                    embed_config = json.loads(entry.embed_config)
                    embed = Embed.from_dict(embed_config)
                    message = None
                else:
                    embed = None
                    message = entry.message

                await tagged_response(ctx, content=message, embed=embed)

                if not self.bot.plugin_api.plugins.get("relay"):
                    return

                if ctx.channel.id in self.bot.plugin_api.plugins.relay.memory.channels:
                    ctx.content = entry.message
                    self.bot.plugin_api.plugins.factoids.memory.factoid_events.append(
                        ctx
                    )
                    while (
                        len(self.bot.plugin_api.plugins.factoids.memory.factoid_events)
                        > 10
                    ):
                        del self.bot.plugin_api.plugins.factoids.memory.factoid_events[
                            0
                        ]

        except Exception as e:
            if isinstance(e, HTTPException) and getattr(e, "code", 0) == 50035:
                await priv_response(ctx, "Unable to render Embed from Factoid...")
                return

            log.warning(f"Unable to get factoid: {e}")
            await priv_response(ctx, "I ran into an issue grabbing your factoid...")
