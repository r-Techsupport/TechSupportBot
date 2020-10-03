import datetime

from discord.ext import commands
from sqlalchemy import Column, DateTime, Integer, String

from cogs import DatabasePlugin, MatchPlugin
from utils.helpers import embed_from_kwargs, priv_response, tagged_response


class Factoid(DatabasePlugin.BaseTable):
    __tablename__ = "factoids"

    pk = Column(Integer, primary_key=True)
    text = Column(String)
    channel = Column(String)
    message = Column(String)
    time = Column(DateTime, default=datetime.datetime.utcnow)


def setup(bot):
    bot.add_cog(FactoidManager(bot, Factoid))


class FactoidManager(DatabasePlugin, MatchPlugin):
    PLUGIN_NAME = __name__

    async def db_preconfig(self):
        factoid_prefix = self.config.prefix
        command_prefix = self.bot.config.main.required.command_prefix

        if factoid_prefix == command_prefix:
            raise RuntimeError(
                f"Command prefix '{command_prefix}' cannot equal Factoid prefix"
            )

    @commands.command(
        name="r",
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
            await priv_response(ctx, "Sorry, factoids don't work well with mentions.")
            return

        if len(args) >= 2:
            arg1 = args[0]
            args = args[1:]

        channel = str(ctx.message.channel.id)

        db = self.db_session()

        try:
            # first check if key already exists
            entry = (
                db.query(Factoid)
                .filter(Factoid.text == arg1, Factoid.channel == channel)
                .first()
            )
            if entry:
                # delete old one
                db.delete(entry)
                await priv_response(
                    ctx, "Deleting previous entry of factoid trigger..."
                )

            # finally, add new entry
            db.add(Factoid(text=arg1.lower(), channel=channel, message=" ".join(args)))
            db.commit()
            await tagged_response(ctx, f"Successfully added factoid trigger: *{arg1}*")

        except Exception as e:
            # await priv_response(
            #     ctx, "I ran into an issue handling your factoid addition..."
            # )
            import logging

            logging.exception(e)

    @commands.command(
        name="f",
        brief="Deletes an existing custom trigger",
        description="Deletes an existing custom trigger.",
        usage="[trigger-name]",
        help="\nLimitations: Mentions should not be used as triggers.",
    )
    async def delete_factoid(self, ctx, *args):
        if ctx.message.mentions:
            await priv_response(ctx, "Sorry, factoids don't work well with mentions.")
            return

        if not args:
            await priv_response(ctx, "You must specify a factoid to delete!")
            return
        else:
            arg = args[0]

        channel = str(ctx.message.channel.id)

        db = self.db_session()

        try:
            entry = (
                db.query(Factoid)
                .filter(Factoid.text == arg, Factoid.channel == channel)
                .first()
            )
            if entry:
                db.delete(entry)
                db.commit()
            await tagged_response(ctx, f"Successfully deleted factoid trigger: *{arg}*")

        except Exception:
            await priv_response(
                ctx, "I ran into an issue handling your factoid deletion..."
            )

    @commands.command(
        name="ls_factoids",
        brief="List all factoids",
        description="Shows an embed with all the factoids",
        usage="",
        help="\nLimitations: Currently only shows up to 20",
    )
    async def list_all_factoids(self, ctx):
        if ctx.message.mentions:
            await priv_response(ctx, "Sorry, factoids don't work well with mentions.")
            return

        db = self.db_session()

        try:
            factoids = db.query(Factoid).all()
        except Exception:
            await priv_response(ctx, "I was unable to get all the factoids...")

        factoid_dict = {}
        for index, factoid in enumerate(factoids):
            factoid_dict[factoid.text] = factoid.message
            # prevent too many factoids from showing
            if index == 20:
                break
        embed = embed_from_kwargs(
            title="Factoids",
            description=f"Access factoids with the `{self.config.prefix}` prefix",
            **factoid_dict,
        )
        await ctx.send(embed=embed)

    def match(self, _, content):
        return bool(content.startswith(self.config.prefix))

    async def response(self, ctx, arg):
        if ctx.message.mentions:
            await priv_response(ctx, "Sorry, factoids don't work well with mentions.")
            return

        channel = str(ctx.message.channel.id)

        db = self.db_session()

        try:
            entry = (
                db.query(Factoid)
                .filter(Factoid.text == arg[1:], Factoid.channel == channel)
                .first()
            )
            if entry:
                await tagged_response(ctx, entry.message)

        except Exception:
            await priv_response("I ran into an issue grabbing your factoid...")
